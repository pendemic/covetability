"""Daily score orchestration in shadow mode (score-spec §7, §8).

For one bag/day: build the guarded price series, compute all five components,
gate + redistribute weights, sum the raw score, smooth (7-day EMA), derive the
publication-track value and direction, compute confidence, classify, and write
one ``score_daily`` row (delete-then-insert, ``published=false``) carrying the
full ``component_trace``. Every material move must be explainable from that row.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.contract import (
    COMPONENT_BREADTH,
    COMPONENT_INVENTORY,
    COMPONENT_KEYS,
    COMPONENT_PRICE,
    COMPONENT_SEARCH,
    COMPONENT_TURNOVER,
    DIRECTION_WINDOW_DAYS,
    SCORE_CLASSIFICATION_BOUNDS,
    ScoreClassification,
)
from app.matching.engine import ACCEPTED_STATUSES
from app.models import BagModel, DailyAggregate, ListingRaw, ScoreDaily, ScoreRun
from app.models.score import ScoreConfig
from app.scoring.components import (
    ComponentResult,
    compute_breadth,
    compute_inventory,
    compute_price,
    compute_search,
    compute_turnover,
)
from app.scoring.confidence import compute_confidence
from app.scoring.gates import redistribute
from app.scoring.price_guard import build_price_points_for_day
from app.scoring.smoothing import direction, ema, publication_value

_COMPONENT_FIELD = {
    COMPONENT_SEARCH: "search",
    COMPONENT_INVENTORY: "inventory",
    COMPONENT_PRICE: "price",
    COMPONENT_BREADTH: "breadth",
    COMPONENT_TURNOVER: "turnover",
}


@dataclass
class ScoreRunSummary:
    observation_date: date
    bags_scored: int = 0
    bags_unscored: int = 0
    bag_stats: dict[str, dict[str, Any]] = field(default_factory=dict)


def classify_score(value: float) -> ScoreClassification:
    rounded = round(value)
    for classification, (low, high) in SCORE_CLASSIFICATION_BOUNDS.items():
        if low <= rounded <= high:
            return classification
    return ScoreClassification.surging if rounded > 100 else ScoreClassification.dormant


def run_daily_score(
    session: Session,
    day: date,
    *,
    relist_precision: float | None = None,
    mode: str = "daily",
) -> ScoreRunSummary:
    summary = ScoreRunSummary(observation_date=day)
    bags = session.scalars(select(BagModel).order_by(BagModel.slug)).all()
    for bag in bags:
        row = compute_bag_day(session, bag, day, relist_precision=relist_precision)
        if row.raw_score is None:
            summary.bags_unscored += 1
        else:
            summary.bags_scored += 1
        summary.bag_stats[bag.slug] = {
            "raw": float(row.raw_score) if row.raw_score is not None else None,
            "smoothed": float(row.smoothed_score) if row.smoothed_score is not None else None,
            "publication": float(row.publication_value) if row.publication_value is not None else None,
            "classification": row.classification.value if row.classification else None,
            "eligible": row.component_trace.get("eligible", []),
            "unscored_reason": row.unscored_reason,
        }

    session.add(
        ScoreRun(
            run_at=datetime.now(UTC),
            mode=mode,
            observation_date=day,
            bags_scored=summary.bags_scored,
            bags_unscored=summary.bags_unscored,
            bag_stats=summary.bag_stats,
        )
    )
    session.flush()
    return summary


def compute_bag_day(
    session: Session,
    bag: BagModel,
    day: date,
    *,
    relist_precision: float | None = None,
) -> ScoreDaily:
    build_price_points_for_day(session, bag.id, day)
    config = score_config(session)
    weight_overrides = (
        {COMPONENT_SEARCH: config.search_weight}
        if config is not None
        else None
    )

    inventory = compute_inventory(session, bag.id, day)
    results: dict[str, ComponentResult] = {
        COMPONENT_SEARCH: compute_search(session, bag.id, day),
        COMPONENT_INVENTORY: inventory,
        COMPONENT_PRICE: compute_price(session, bag.id, day, inventory=inventory),
        COMPONENT_TURNOVER: compute_turnover(session, bag.id, day, relist_precision=relist_precision),
        COMPONENT_BREADTH: compute_breadth(session, bag.id, day),
    }
    if config is not None and config.search_weight == 0:
        search = results[COMPONENT_SEARCH]
        results[COMPONENT_SEARCH] = ComponentResult(
            search.key,
            search.value,
            False,
            "search stability decision excluded S",
            search.trace,
        )

    redis = redistribute(
        {key: results[key].eligible for key in COMPONENT_KEYS},
        weight_overrides=weight_overrides,
    )
    matched_count, avg_confidence = _coverage(session, bag.id, day)
    history_days = _history_days(session, bag.id, day)
    source_count = int(results[COMPONENT_BREADTH].trace.get("source_count", 0))
    excluded = 5 - len(redis.eligible)

    components_trace: dict[str, Any] = {}
    raw: float | None = None
    if redis.scored:
        raw = 0.0
        for key in COMPONENT_KEYS:
            weight = redis.weights[key]
            value = results[key].value
            contribution = round(weight / 100 * value, 4) if (results[key].eligible and value is not None) else 0.0
            raw += contribution
            components_trace[key] = _component_entry(results[key], weight, contribution)
        raw = round(raw, 2)
    else:
        for key in COMPONENT_KEYS:
            components_trace[key] = _component_entry(results[key], 0.0, 0.0)

    previous = _previous_scored(session, bag.id, day)
    smoothed = None
    pub_value = None
    row_direction = None
    classification = None
    if raw is not None:
        prev_smoothed = float(previous.smoothed_score) if previous and previous.smoothed_score is not None else None
        smoothed = ema(prev_smoothed, raw)
        prev_pub = float(previous.publication_value) if previous and previous.publication_value is not None else None
        pub_value = publication_value(prev_pub, smoothed)
        classification = classify_score(smoothed)
        row_direction = direction(_publication_series(session, bag.id, day, pub_value))

    confidence = compute_confidence(
        matched_listing_count=matched_count,
        history_days=history_days,
        average_match_confidence=avg_confidence,
        eligible_component_count=len(redis.eligible),
        source_count=source_count,
        excluded_component_count=excluded,
    )

    trace = {
        "scored": redis.scored,
        "raw_score": raw,
        "smoothed_score": smoothed,
        "publication_value": pub_value,
        "direction": row_direction.value if row_direction else None,
        "classification": classification.value if classification else None,
        "weights": redis.weights,
        "weight_overrides": weight_overrides or {},
        "eligible": redis.eligible,
        "overflow_to": redis.overflow_to,
        "unscored_reason": redis.unscored_reason,
        "confidence": {
            "value": confidence.value,
            "raw": confidence.raw,
            "caps_applied": confidence.caps_applied,
        },
        "inputs": {
            "matched_listing_count": matched_count,
            "history_days": history_days,
            "source_count": source_count,
            "average_match_confidence": round(avg_confidence, 4),
            "excluded_component_count": excluded,
        },
        "components": components_trace,
    }

    session.execute(
        delete(ScoreDaily).where(
            ScoreDaily.bag_model_id == bag.id, ScoreDaily.observation_date == day
        )
    )
    row = ScoreDaily(
        bag_model_id=bag.id,
        observation_date=day,
        raw_score=_dec(raw),
        smoothed_score=_dec(smoothed),
        publication_value=_dec(pub_value),
        direction=row_direction,
        confidence_raw=Decimal(str(confidence.value)),
        classification=classification,
        unscored_reason=redis.unscored_reason,
        published=bag.score_published,
        component_trace=trace,
        **_component_columns(results, redis.weights),
    )
    session.add(row)
    session.flush()
    return row


def score_config(session: Session) -> ScoreConfig | None:
    return session.get(ScoreConfig, 1)


def _component_entry(result: ComponentResult, weight: float, contribution: float) -> dict[str, Any]:
    return {
        "value": result.value,
        "eligible": result.eligible,
        "reason": result.reason,
        "weight": weight,
        "contribution": contribution,
        "trace": result.trace,
    }


def _component_columns(results: dict[str, ComponentResult], weights: dict[str, float]) -> dict[str, Any]:
    columns: dict[str, Any] = {}
    for key, prefix in _COMPONENT_FIELD.items():
        result = results[key]
        columns[f"{prefix}_component_value"] = _dec(result.value)
        columns[f"{prefix}_eligible"] = result.eligible
        columns[f"{prefix}_weight_used"] = Decimal(str(round(weights[key], 2)))
    return columns


def _dec(value: float | None) -> Decimal | None:
    return None if value is None else Decimal(str(round(value, 2)))


def _coverage(session: Session, bag_id: int, day: date) -> tuple[int, float]:
    listings = session.scalars(
        select(ListingRaw).where(
            ListingRaw.matched_bag_model_id == bag_id,
            ListingRaw.match_status.in_(ACCEPTED_STATUSES),
        )
    ).all()
    active = [
        listing
        for listing in listings
        if listing.first_observed.date() <= day <= listing.last_observed.date()
    ]
    if not active:
        return 0, 0.0
    confidences = [float(listing.match_confidence) for listing in active if listing.match_confidence is not None]
    avg = sum(confidences) / len(confidences) if confidences else 0.0
    return len(active), avg


def _history_days(session: Session, bag_id: int, day: date) -> int:
    return int(
        session.scalar(
            select(func.count(func.distinct(DailyAggregate.observation_date))).where(
                DailyAggregate.bag_model_id == bag_id,
                DailyAggregate.observation_date <= day,
            )
        )
        or 0
    )


def _previous_scored(session: Session, bag_id: int, day: date) -> ScoreDaily | None:
    return session.scalars(
        select(ScoreDaily)
        .where(
            ScoreDaily.bag_model_id == bag_id,
            ScoreDaily.observation_date < day,
            ScoreDaily.raw_score.is_not(None),
        )
        .order_by(ScoreDaily.observation_date.desc())
        .limit(1)
    ).first()


def _publication_series(session: Session, bag_id: int, day: date, today_value: float) -> list[float]:
    window_start = day - timedelta(days=DIRECTION_WINDOW_DAYS - 1)
    rows = session.scalars(
        select(ScoreDaily)
        .where(
            ScoreDaily.bag_model_id == bag_id,
            ScoreDaily.observation_date >= window_start,
            ScoreDaily.observation_date < day,
            ScoreDaily.publication_value.is_not(None),
        )
        .order_by(ScoreDaily.observation_date)
    ).all()
    series = [float(row.publication_value) for row in rows]
    series.append(today_value)
    return series
