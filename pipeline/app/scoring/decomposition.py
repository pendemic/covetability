from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contract import COMPONENT_KEYS
from app.models import ScoreDaily


@dataclass(frozen=True)
class ComponentDelta:
    component: str
    contribution_now: float
    contribution_previous: float
    delta: float
    value: float | None
    eligible: bool | None
    reason: str | None
    trace: dict[str, Any]


@dataclass(frozen=True)
class ScoreDecomposition:
    date: date
    previous_date: date | None
    raw_now: float
    raw_previous: float
    raw_delta: float
    decomposition_sum: float
    components: list[ComponentDelta]


def decompose_score_day(session: Session, bag_id: int, day: date) -> ScoreDecomposition | None:
    current = _row_on(session, bag_id, day)
    if current is None:
        return None
    previous = session.scalars(
        select(ScoreDaily)
        .where(
            ScoreDaily.bag_model_id == bag_id,
            ScoreDaily.observation_date < day,
            ScoreDaily.raw_score.is_not(None),
        )
        .order_by(ScoreDaily.observation_date.desc())
        .limit(1)
    ).first()

    now_components = (current.component_trace or {}).get("components", {})
    prev_components = (previous.component_trace or {}).get("components", {}) if previous else {}
    parts: list[ComponentDelta] = []
    total = 0.0
    for key in COMPONENT_KEYS:
        now_entry = now_components.get(key, {})
        prev_entry = prev_components.get(key, {})
        now_c = float(now_entry.get("contribution", 0.0) or 0.0)
        prev_c = float(prev_entry.get("contribution", 0.0) or 0.0)
        delta = round(now_c - prev_c, 4)
        total += delta
        parts.append(
            ComponentDelta(
                component=key,
                contribution_now=round(now_c, 4),
                contribution_previous=round(prev_c, 4),
                delta=delta,
                value=now_entry.get("value"),
                eligible=now_entry.get("eligible"),
                reason=now_entry.get("reason"),
                trace=now_entry.get("trace") or {},
            )
        )

    raw_now = float(current.raw_score) if current.raw_score is not None else 0.0
    raw_prev = float(previous.raw_score) if previous and previous.raw_score is not None else 0.0
    return ScoreDecomposition(
        date=day,
        previous_date=previous.observation_date if previous else None,
        raw_now=round(raw_now, 2),
        raw_previous=round(raw_prev, 2),
        raw_delta=round(raw_now - raw_prev, 2),
        decomposition_sum=round(total, 2),
        components=parts,
    )


def _row_on(session: Session, bag_id: int, day: date) -> ScoreDaily | None:
    return session.scalars(
        select(ScoreDaily).where(
            ScoreDaily.bag_model_id == bag_id,
            ScoreDaily.observation_date == day,
        )
    ).first()
