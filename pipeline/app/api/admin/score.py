"""Admin score-audit API — the shadow-mode instrument (score-spec §7, §8).

Every material score move must be explainable from these endpoints alone: the
timeline, the per-day component trace, the day-over-day decomposition (whose
contributions sum to the actual raw delta), the gate-status history, and the
weekly search signal.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.api.admin.deps import SessionDep
from app.contract import COMPONENT_KEYS
from app.models import BagModel, ScoreDaily, SearchSignalWeekly

router = APIRouter()


def _bag_or_404(session: SessionDep, slug: str) -> BagModel:
    bag = session.scalars(select(BagModel).where(BagModel.slug == slug)).first()
    if bag is None:
        raise HTTPException(status_code=404, detail="bag not found")
    return bag


@router.get("/score/bags")
def score_bags(session: SessionDep) -> dict[str, Any]:
    bags = session.scalars(select(BagModel).order_by(BagModel.slug)).all()
    out = []
    for bag in bags:
        latest = session.scalars(
            select(ScoreDaily)
            .where(ScoreDaily.bag_model_id == bag.id)
            .order_by(ScoreDaily.observation_date.desc())
            .limit(1)
        ).first()
        out.append(
            {
                "slug": bag.slug,
                "model_name": bag.model_name,
                "latest_date": latest.observation_date.isoformat() if latest else None,
                "raw_score": _num(latest.raw_score) if latest else None,
                "publication_value": _num(latest.publication_value) if latest else None,
                "classification": latest.classification.value if latest and latest.classification else None,
                "unscored_reason": latest.unscored_reason if latest else None,
            }
        )
    return {"bags": out, "published": False}


@router.get("/score/{slug}/timeline")
def score_timeline(session: SessionDep, slug: str, days: int = Query(default=120, ge=1, le=400)) -> dict[str, Any]:
    bag = _bag_or_404(session, slug)
    rows = session.scalars(
        select(ScoreDaily)
        .where(ScoreDaily.bag_model_id == bag.id)
        .order_by(ScoreDaily.observation_date.desc())
        .limit(days)
    ).all()
    timeline = [
        {
            "date": row.observation_date.isoformat(),
            "raw_score": _num(row.raw_score),
            "smoothed_score": _num(row.smoothed_score),
            "publication_value": _num(row.publication_value),
            "classification": row.classification.value if row.classification else None,
            "direction": row.direction.value if row.direction else None,
            "confidence": _num(row.confidence_raw),
            "scored": row.raw_score is not None,
            "unscored_reason": row.unscored_reason,
            "weights": (row.component_trace or {}).get("weights", {}),
        }
        for row in reversed(rows)
    ]
    return {"slug": slug, "model_name": bag.model_name, "published": False, "timeline": timeline}


@router.get("/score/{slug}/trace")
def score_trace(session: SessionDep, slug: str, date: str = Query(...)) -> dict[str, Any]:
    bag = _bag_or_404(session, slug)
    row = _row_on(session, bag.id, _parse(date))
    if row is None:
        raise HTTPException(status_code=404, detail="no score for that date")
    return {"slug": slug, "date": row.observation_date.isoformat(), "trace": row.component_trace}


@router.get("/score/{slug}/decomposition")
def score_decomposition(session: SessionDep, slug: str, date: str = Query(...)) -> dict[str, Any]:
    bag = _bag_or_404(session, slug)
    day = _parse(date)
    current = _row_on(session, bag.id, day)
    if current is None:
        raise HTTPException(status_code=404, detail="no score for that date")
    previous = session.scalars(
        select(ScoreDaily)
        .where(
            ScoreDaily.bag_model_id == bag.id,
            ScoreDaily.observation_date < day,
            ScoreDaily.raw_score.is_not(None),
        )
        .order_by(ScoreDaily.observation_date.desc())
        .limit(1)
    ).first()

    now_components = (current.component_trace or {}).get("components", {})
    prev_components = (previous.component_trace or {}).get("components", {}) if previous else {}
    parts = []
    total = 0.0
    for key in COMPONENT_KEYS:
        now_c = float(now_components.get(key, {}).get("contribution", 0.0) or 0.0)
        prev_c = float(prev_components.get(key, {}).get("contribution", 0.0) or 0.0)
        delta = round(now_c - prev_c, 4)
        total += delta
        parts.append(
            {
                "component": key,
                "contribution_now": round(now_c, 4),
                "contribution_previous": round(prev_c, 4),
                "delta": delta,
                "value": now_components.get(key, {}).get("value"),
                "eligible": now_components.get(key, {}).get("eligible"),
                "reason": now_components.get(key, {}).get("reason"),
            }
        )

    raw_now = float(current.raw_score) if current.raw_score is not None else 0.0
    raw_prev = float(previous.raw_score) if previous and previous.raw_score is not None else 0.0
    raw_delta = round(raw_now - raw_prev, 2)
    return {
        "slug": slug,
        "date": day.isoformat(),
        "previous_date": previous.observation_date.isoformat() if previous else None,
        "raw_now": round(raw_now, 2),
        "raw_previous": round(raw_prev, 2),
        "raw_delta": raw_delta,
        "decomposition_sum": round(total, 2),
        "components": parts,
    }


@router.get("/score/{slug}/gates")
def score_gates(session: SessionDep, slug: str, days: int = Query(default=60, ge=1, le=400)) -> dict[str, Any]:
    bag = _bag_or_404(session, slug)
    rows = session.scalars(
        select(ScoreDaily)
        .where(ScoreDaily.bag_model_id == bag.id)
        .order_by(ScoreDaily.observation_date.desc())
        .limit(days)
    ).all()
    history = []
    for row in reversed(rows):
        components = (row.component_trace or {}).get("components", {})
        history.append(
            {
                "date": row.observation_date.isoformat(),
                "components": {
                    key: {
                        "eligible": components.get(key, {}).get("eligible"),
                        "reason": components.get(key, {}).get("reason"),
                        "weight": components.get(key, {}).get("weight"),
                    }
                    for key in COMPONENT_KEYS
                },
            }
        )
    return {"slug": slug, "gate_history": history}


@router.get("/score/{slug}/search-signal")
def search_signal(session: SessionDep, slug: str, weeks: int = Query(default=52, ge=1, le=200)) -> dict[str, Any]:
    bag = _bag_or_404(session, slug)
    rows = session.scalars(
        select(SearchSignalWeekly)
        .where(SearchSignalWeekly.bag_model_id == bag.id)
        .order_by(SearchSignalWeekly.week_start.desc())
        .limit(weeks)
    ).all()
    signal = [
        {
            "week_start": row.week_start.isoformat(),
            "stitched_value": _num(row.stitched_value),
            "slope_8w": _num(row.slope_8w),
            "slope_4w": _num(row.slope_4w),
            "bucket": row.bucket.value if row.bucket else None,
            "alias_agrees": row.alias_agrees,
            "low_volume": row.low_volume,
            "series_length": row.series_length,
        }
        for row in reversed(rows)
    ]
    return {"slug": slug, "search_signal": signal}


def _row_on(session: SessionDep, bag_id: int, day: date) -> ScoreDaily | None:
    return session.scalars(
        select(ScoreDaily).where(
            ScoreDaily.bag_model_id == bag_id, ScoreDaily.observation_date == day
        )
    ).first()


def _parse(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD") from exc


def _num(value: Any) -> float | None:
    return None if value is None else float(value)
