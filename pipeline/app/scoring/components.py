"""Score v0 component calculators S/I/P/T/B (score-spec §3).

Each calculator returns a ``ComponentResult`` carrying the 0-100 value, an
eligibility flag with a human reason, and a trace dict that the daily audit
screen renders. Durable sources only, so the series survive raw-row expiry:
S from ``search_signal_weekly``, I from ``daily_aggregates``, P from
``score_price_points``, T from ``listing_events``, B from source counts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.contract import (
    BREADTH_LADDER,
    BREADTH_LADDER_MAX_SCORE,
    BREADTH_WINDOW_DAYS,
    COMPONENT_BREADTH,
    COMPONENT_INVENTORY,
    COMPONENT_PRICE,
    COMPONENT_SEARCH,
    COMPONENT_TURNOVER,
    INVENTORY_MIN_HISTORY_DAYS,
    INVENTORY_MOMENTUM_LADDER,
    INVENTORY_SMOOTHING_DAYS,
    INVENTORY_WINDOW_DAYS,
    MIN_LIFECYCLE_EVENTS,
    MIN_MODEL_WIDE_LISTINGS,
    PRICE_BAND_MIX_WEIGHTS,
    PRICE_DIVERGENCE_EXCLUDE_WEEKS,
    PRICE_DIVERGENCE_HALVE_WEEKS,
    PRICE_DIVERGENCE_STRONG_THRESHOLD,
    PRICE_LONG_WINDOW_DAYS,
    PRICE_MAX_UNUSABLE_CONDITION_SHARE,
    PRICE_MOMENTUM_LADDER,
    PRICE_SHORT_LONG_WEIGHTS,
    PRICE_SHORT_WINDOW_DAYS,
    RELIST_PRECISION_TARGET,
    SEARCH_BUCKET_SCORES,
    SEARCH_MIN_SERIES_WEEKS,
    TURNOVER_DEFAULT_INELIGIBLE_REASON,
    TURNOVER_WINDOW_DAYS,
    ConditionBand,
    ListingEventType,
    SearchBucket,
)
from app.matching.engine import ACCEPTED_STATUSES
from app.models import (
    DailyAggregate,
    ListingEvent,
    ListingRaw,
    ManualComp,
    ScorePricePoint,
    SearchSignalWeekly,
)
from app.scoring.util import map_ladder, pct_change

_NEGATIVE_BUCKETS = {SearchBucket.flat, SearchBucket.down, SearchBucket.strong_down}


@dataclass
class ComponentResult:
    key: str
    value: float | None
    eligible: bool
    reason: str | None
    trace: dict[str, Any]


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def _rolling_mean(series: list[float], window: int) -> list[float]:
    out: list[float] = []
    for i in range(len(series)):
        start = max(0, i - window + 1)
        chunk = series[start : i + 1]
        out.append(sum(chunk) / len(chunk))
    return out


# --- S -----------------------------------------------------------------------


def compute_search(session: Session, bag_id: int, day: date) -> ComponentResult:
    signal = session.scalars(
        select(SearchSignalWeekly)
        .where(SearchSignalWeekly.bag_model_id == bag_id, SearchSignalWeekly.week_start <= day)
        .order_by(SearchSignalWeekly.week_start.desc())
        .limit(1)
    ).first()
    if signal is None or signal.bucket is None:
        return ComponentResult(COMPONENT_SEARCH, None, False, "no search signal", {})

    value = float(SEARCH_BUCKET_SCORES[signal.bucket])
    trace = {
        "week_start": signal.week_start.isoformat(),
        "bucket": signal.bucket.value,
        "series_length": signal.series_length,
        "low_volume": signal.low_volume,
        "alias_agrees": signal.alias_agrees,
        "slope_8w": float(signal.slope_8w) if signal.slope_8w is not None else None,
    }

    if signal.series_length < SEARCH_MIN_SERIES_WEEKS:
        return ComponentResult(COMPONENT_SEARCH, value, False, "search series too short (<16 weeks)", trace)
    if signal.low_volume:
        return ComponentResult(COMPONENT_SEARCH, value, False, "sub-threshold search volume", trace)
    if signal.alias_agrees is False:
        return ComponentResult(COMPONENT_SEARCH, value, False, "alias queries disagree in direction", trace)
    return ComponentResult(COMPONENT_SEARCH, value, True, None, trace)


# --- I -----------------------------------------------------------------------


def compute_inventory(session: Session, bag_id: int, day: date) -> ComponentResult:
    window_start = day - timedelta(days=INVENTORY_WINDOW_DAYS - 1)
    rows = session.execute(
        select(DailyAggregate.observation_date, func.sum(DailyAggregate.active_listing_count))
        .where(
            DailyAggregate.bag_model_id == bag_id,
            DailyAggregate.observation_date >= window_start,
            DailyAggregate.observation_date <= day,
        )
        .group_by(DailyAggregate.observation_date)
        .order_by(DailyAggregate.observation_date)
    ).all()

    if not rows:
        return ComponentResult(COMPONENT_INVENTORY, None, False, "no inventory history", {})

    dates = [r[0] for r in rows]
    series = [float(r[1] or 0) for r in rows]
    history_days = len(dates)
    latest_active = series[-1]
    smoothed = _rolling_mean(series, INVENTORY_SMOOTHING_DAYS)
    momentum = pct_change(smoothed[0], smoothed[-1])
    value = float(map_ladder(-momentum, INVENTORY_MOMENTUM_LADDER))
    trace = {
        "history_days": history_days,
        "latest_active": latest_active,
        "baseline_smoothed": round(smoothed[0], 3),
        "recent_smoothed": round(smoothed[-1], 3),
        "momentum": round(momentum, 4),
    }

    if history_days < INVENTORY_MIN_HISTORY_DAYS:
        return ComponentResult(
            COMPONENT_INVENTORY, value, False, "insufficient snapshot history (<45 days)", trace
        )
    if latest_active < MIN_MODEL_WIDE_LISTINGS:
        return ComponentResult(
            COMPONENT_INVENTORY, value, False, "insufficient active listings (<8 model-wide)", trace
        )
    return ComponentResult(COMPONENT_INVENTORY, value, True, None, trace)


def inventory_momentum(result: ComponentResult) -> float:
    return float(result.trace.get("momentum", 0.0) or 0.0)


# --- P -----------------------------------------------------------------------


def compute_price(
    session: Session,
    bag_id: int,
    day: date,
    *,
    inventory: ComponentResult,
) -> ComponentResult:
    long_start = day - timedelta(days=PRICE_LONG_WINDOW_DAYS - 1)
    short_start = day - timedelta(days=PRICE_SHORT_WINDOW_DAYS - 1)
    points = session.scalars(
        select(ScorePricePoint)
        .where(
            ScorePricePoint.bag_model_id == bag_id,
            ScorePricePoint.observation_date >= long_start,
            ScorePricePoint.observation_date <= day,
            ScorePricePoint.guarded_median.is_not(None),
        )
        .order_by(ScorePricePoint.observation_date)
    ).all()

    model_wide, unusable_share = _price_coverage(session, bag_id, day)
    trace: dict[str, Any] = {
        "model_wide_active": model_wide,
        "unusable_condition_share": round(unusable_share, 3),
        "bands": {},
    }

    if model_wide < MIN_MODEL_WIDE_LISTINGS:
        return ComponentResult(COMPONENT_PRICE, None, False, "insufficient listings (<8 model-wide)", trace)
    if unusable_share > PRICE_MAX_UNUSABLE_CONDITION_SHARE:
        return ComponentResult(COMPONENT_PRICE, None, False, "condition unusable on >40% of listings", trace)

    by_band: dict[ConditionBand, list[tuple[date, float]]] = {}
    for point in points:
        by_band.setdefault(point.condition_band, []).append(
            (point.observation_date, float(point.guarded_median))
        )

    w_short, w_long = PRICE_SHORT_LONG_WEIGHTS
    band_momenta: dict[ConditionBand, float] = {}
    for band, series in by_band.items():
        if len(series) < 2:
            continue
        latest = series[-1][1]
        short_base = next((v for d, v in series if d >= short_start), series[0][1])
        long_base = series[0][1]
        band_momentum = w_short * pct_change(short_base, latest) + w_long * pct_change(long_base, latest)
        band_momenta[band] = band_momentum
        trace["bands"][band.value] = {
            "points": len(series),
            "short_momentum": round(pct_change(short_base, latest), 4),
            "long_momentum": round(pct_change(long_base, latest), 4),
        }

    if not band_momenta:
        return ComponentResult(COMPONENT_PRICE, None, False, "insufficient priced-band history", trace)

    weight_total = sum(PRICE_BAND_MIX_WEIGHTS[band] for band in band_momenta)
    blended = sum(PRICE_BAND_MIX_WEIGHTS[band] * m for band, m in band_momenta.items()) / weight_total
    value = float(map_ladder(blended, PRICE_MOMENTUM_LADDER))
    trace["blended_momentum"] = round(blended, 4)

    # Divergence guard: strong price rise while search + inventory are flat/negative.
    consec = _consecutive_flat_negative_weeks(session, bag_id, day)
    inv_momentum = inventory_momentum(inventory)
    diverging = value >= PRICE_DIVERGENCE_STRONG_THRESHOLD and inv_momentum <= 0
    trace["divergence"] = {"consecutive_flat_neg_weeks": consec, "inventory_momentum": round(inv_momentum, 4)}

    if diverging and consec >= PRICE_DIVERGENCE_EXCLUDE_WEEKS:
        return ComponentResult(
            COMPONENT_PRICE, value, False, "seller-led repricing (8+ week divergence)", trace
        )
    if diverging and consec >= PRICE_DIVERGENCE_HALVE_WEEKS:
        halved = value / 2
        trace["halved_from"] = value
        return ComponentResult(COMPONENT_PRICE, halved, True, "seller-led repricing (divergence)", trace)
    return ComponentResult(COMPONENT_PRICE, value, True, None, trace)


def _price_coverage(session: Session, bag_id: int, day: date) -> tuple[int, float]:
    listings = session.scalars(
        select(ListingRaw).where(
            ListingRaw.matched_bag_model_id == bag_id,
            ListingRaw.match_status.in_(ACCEPTED_STATUSES),
            ListingRaw.currency == "USD",
        )
    ).all()
    active = [
        listing
        for listing in listings
        if listing.first_observed.date() <= day <= listing.last_observed.date()
    ]
    if not active:
        return 0, 0.0
    unusable = sum(1 for listing in active if listing.condition_band is None)
    return len(active), unusable / len(active)


def _consecutive_flat_negative_weeks(session: Session, bag_id: int, day: date) -> int:
    weeks = session.scalars(
        select(SearchSignalWeekly)
        .where(SearchSignalWeekly.bag_model_id == bag_id, SearchSignalWeekly.week_start <= day)
        .order_by(SearchSignalWeekly.week_start.desc())
    ).all()
    consec = 0
    for week in weeks:
        if week.bucket in _NEGATIVE_BUCKETS:
            consec += 1
        else:
            break
    return consec


# --- T -----------------------------------------------------------------------


def compute_turnover(
    session: Session,
    bag_id: int,
    day: date,
    *,
    relist_precision: float | None = None,
) -> ComponentResult:
    window_start = day - timedelta(days=TURNOVER_WINDOW_DAYS - 1)
    counts = dict(
        session.execute(
            select(ListingEvent.type, func.count())
            .join(ListingRaw, ListingRaw.id == ListingEvent.listing_id)
            .where(
                ListingRaw.matched_bag_model_id == bag_id,
                ListingEvent.event_date >= window_start,
                ListingEvent.event_date <= day,
            )
            .group_by(ListingEvent.type)
        ).all()
    )
    ended = int(counts.get(ListingEventType.ended, 0))
    relist = int(counts.get(ListingEventType.possible_relist, 0))
    lifecycle = ended + relist
    rate = (ended - relist) / ended if ended > 0 else 0.0
    value = float(max(0.0, min(1.0, rate)) * 100)
    trace = {
        "ended": ended,
        "possible_relist": relist,
        "lifecycle_events": lifecycle,
        "ended_not_relisted_rate": round(rate, 4),
        "relist_precision": relist_precision,
    }

    if relist_precision is None or relist_precision <= RELIST_PRECISION_TARGET:
        return ComponentResult(COMPONENT_TURNOVER, value, False, TURNOVER_DEFAULT_INELIGIBLE_REASON, trace)
    if lifecycle < MIN_LIFECYCLE_EVENTS:
        return ComponentResult(
            COMPONENT_TURNOVER, value, False, "insufficient lifecycle events (<15)", trace
        )
    return ComponentResult(COMPONENT_TURNOVER, value, True, None, trace)


# --- B -----------------------------------------------------------------------


def compute_breadth(session: Session, bag_id: int, day: date) -> ComponentResult:
    window_start = _day_start(day - timedelta(days=BREADTH_WINDOW_DAYS - 1))
    api_sources = set(
        session.scalars(
            select(ListingRaw.source)
            .where(
                ListingRaw.matched_bag_model_id == bag_id,
                ListingRaw.match_status.in_(ACCEPTED_STATUSES),
                ListingRaw.last_observed >= window_start,
            )
            .distinct()
        ).all()
    )
    manual_sources = set(
        session.scalars(
            select(ManualComp.source)
            .where(
                ManualComp.bag_model_id == bag_id,
                ManualComp.observed_at >= window_start,
                ManualComp.source.is_not(None),
            )
            .distinct()
        ).all()
    )
    sources = {s for s in api_sources | manual_sources if s}
    count = len(sources)
    value = float(BREADTH_LADDER_MAX_SCORE if count >= 5 else BREADTH_LADDER.get(count, 0))
    return ComponentResult(
        COMPONENT_BREADTH,
        value,
        True,
        None,
        {"source_count": count, "sources": sorted(sources)},
    )
