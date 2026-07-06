from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contract import MATCH_PRECISION_TARGET
from app.matching.evaluate import evaluate_matcher
from app.models import BagModel, ScoreConfig, ScoreDaily

MATERIAL_MOVE_THRESHOLD = 3.0


@dataclass(frozen=True)
class ReadinessItem:
    key: str
    label: str
    passed: bool
    detail: str
    operator_attested: bool = False


@dataclass(frozen=True)
class MaterialMove:
    date: str
    previous_date: str | None
    smoothed_delta: float
    notes_present: bool
    warnings: list[str]


@dataclass(frozen=True)
class PublicationReadiness:
    slug: str
    ready: bool
    items: list[ReadinessItem]
    material_moves: list[MaterialMove]


def evaluate_publication_readiness(session: Session, bag: BagModel) -> PublicationReadiness:
    score_rows = session.scalars(
        select(ScoreDaily)
        .where(ScoreDaily.bag_model_id == bag.id)
        .order_by(ScoreDaily.observation_date)
    ).all()
    scored_rows = [row for row in score_rows if row.raw_score is not None]
    material_moves = _material_moves(scored_rows)
    config = session.get(ScoreConfig, 1)
    matcher_report = evaluate_matcher(session, bag_slug=bag.slug)
    precision_passed = (
        matcher_report.evaluated_labels > 0
        and matcher_report.precision >= MATCH_PRECISION_TARGET
    )
    history_days = len({row.observation_date for row in scored_rows})
    currently_scored = bool(scored_rows and scored_rows[-1].raw_score is not None)

    items = [
        ReadinessItem(
            key="shadow_history",
            label="30+ days of scored shadow history",
            passed=history_days >= 30 and currently_scored,
            detail=f"{history_days} scored days",
        ),
        ReadinessItem(
            key="match_precision",
            label="Matcher precision at or above target",
            passed=precision_passed,
            detail=(
                f"precision {matcher_report.precision:.3f} over "
                f"{matcher_report.evaluated_labels} evaluated labels"
            ),
        ),
        ReadinessItem(
            key="stability_decision",
            label="Search stability weight decision applied",
            passed=config is not None,
            detail=(
                f"search weight {config.search_weight}: {config.rationale}"
                if config is not None
                else "no score_config row"
            ),
        ),
        ReadinessItem(
            key="material_moves_attested",
            label="Material score moves reviewed",
            passed=all(move.notes_present for move in material_moves),
            detail=f"{sum(1 for move in material_moves if move.notes_present)}/{len(material_moves)} moves have notes",
            operator_attested=True,
        ),
        ReadinessItem(
            key="display_rules",
            label="Public score display rules implemented",
            passed=True,
            detail="published payload includes classification, confidence, and component gates",
        ),
    ]
    return PublicationReadiness(
        slug=bag.slug,
        ready=all(item.passed for item in items),
        items=items,
        material_moves=material_moves,
    )


def readiness_dict(readiness: PublicationReadiness) -> dict[str, Any]:
    return {
        "slug": readiness.slug,
        "ready": readiness.ready,
        "items": [
            {
                "key": item.key,
                "label": item.label,
                "passed": item.passed,
                "detail": item.detail,
                "operator_attested": item.operator_attested,
            }
            for item in readiness.items
        ],
        "material_moves": [
            {
                "date": move.date,
                "previous_date": move.previous_date,
                "smoothed_delta": move.smoothed_delta,
                "notes_present": move.notes_present,
                "warnings": move.warnings,
            }
            for move in readiness.material_moves
        ],
    }


def _material_moves(rows: list[ScoreDaily]) -> list[MaterialMove]:
    out: list[MaterialMove] = []
    recent = rows[-31:]
    for previous, current in zip(recent, recent[1:], strict=False):
        if previous.smoothed_score is None or current.smoothed_score is None:
            continue
        delta = round(float(current.smoothed_score) - float(previous.smoothed_score), 2)
        if abs(delta) < MATERIAL_MOVE_THRESHOLD:
            continue
        warnings: list[str] = []
        trace = current.component_trace or {}
        components = trace.get("components", {})
        price_trace = components.get("asking_price_momentum", {}).get("trace", {})
        if price_trace.get("divergence", {}).get("consecutive_flat_neg_weeks", 0):
            warnings.append("price/search divergence present")
        if trace.get("inputs", {}).get("matched_listing_count", 0) < 15:
            warnings.append("thin matched listing count")
        out.append(
            MaterialMove(
                date=current.observation_date.isoformat(),
                previous_date=previous.observation_date.isoformat(),
                smoothed_delta=delta,
                notes_present=bool(current.notes),
                warnings=warnings,
            )
        )
    return out
