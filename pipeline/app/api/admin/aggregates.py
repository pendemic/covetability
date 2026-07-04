from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.admin.deps import SessionDep
from app.contract import ConditionBand
from app.matching.engine import ACCEPTED_STATUSES
from app.models import AggregateRun, BagModel, DailyAggregate, ListingRaw, SnapshotRun

router = APIRouter()


@router.get("/quality/summary")
def quality_summary(
    session: SessionDep,
    days: int = Query(default=14, ge=1, le=90),
) -> dict[str, Any]:
    end_date = datetime.now(UTC).date()
    start_date = end_date - timedelta(days=days - 1)
    bags = session.scalars(select(BagModel).order_by(BagModel.slug)).all()
    aggregate_rows = session.scalars(
        select(DailyAggregate).where(
            DailyAggregate.observation_date >= start_date,
            DailyAggregate.observation_date <= end_date,
        )
    ).all()
    latest_run = session.scalar(select(AggregateRun).order_by(AggregateRun.run_at.desc()).limit(1))
    return {
        "date_from": start_date.isoformat(),
        "date_to": end_date.isoformat(),
        "bags": [
            bag_quality(session, bag, aggregate_rows, latest_run, start_date, end_date) for bag in bags
        ],
        "alarms": quality_alarms(session, start_date, end_date),
    }


def bag_quality(
    session,
    bag: BagModel,
    aggregate_rows: list[DailyAggregate],
    latest_run: AggregateRun | None,
    start_date,
    end_date,
) -> dict[str, Any]:
    rows = [row for row in aggregate_rows if row.bag_model_id == bag.id]
    band_coverage: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        date_key = row.observation_date.isoformat()
        band_coverage.setdefault(date_key, {})
        band_coverage[date_key][row.condition_band.value] = {
            "matched": row.matched_listing_count,
            "priced": row.median_asking_price is not None,
            "variant_id": row.variant_id,
        }

    active_by_date: dict[str, int] = {}
    confidence_by_date: dict[str, list[float]] = {}
    separate_rows = 0
    for row in rows:
        date_key = row.observation_date.isoformat()
        active_by_date[date_key] = active_by_date.get(date_key, 0) + row.active_listing_count
        if row.average_match_confidence is not None:
            confidence_by_date.setdefault(date_key, []).append(float(row.average_match_confidence))
        if row.variant_id is not None:
            separate_rows += 1

    accepted_count = session.scalar(
        select(func.count()).select_from(ListingRaw).where(
            ListingRaw.matched_bag_model_id == bag.id,
            ListingRaw.match_status.in_(ACCEPTED_STATUSES),
        )
    ) or 0
    variant_count = session.scalar(
        select(func.count()).select_from(ListingRaw).where(
            ListingRaw.matched_bag_model_id == bag.id,
            ListingRaw.match_status.in_(ACCEPTED_STATUSES),
            ListingRaw.matched_variant_id.is_not(None),
        )
    ) or 0
    latest_stats = (latest_run.bag_stats or {}).get(bag.slug, {}) if latest_run else {}
    window_listings = int(latest_stats.get("window_listings", 0) or 0)
    unbanded = int(latest_stats.get("unbanded_matched", 0) or 0)

    return {
        "bag_slug": bag.slug,
        "band_coverage": fill_band_dates(band_coverage, start_date, end_date),
        "active_trend": [
            {"date": day, "count": active_by_date.get(day, 0)}
            for day in date_keys(start_date, end_date)
        ],
        "confidence_trend": [
            {
                "date": day,
                "average": (
                    sum(confidence_by_date[day]) / len(confidence_by_date[day])
                    if day in confidence_by_date
                    else None
                ),
            }
            for day in date_keys(start_date, end_date)
        ],
        "unbanded_share": 0 if window_listings == 0 else unbanded / window_listings,
        "variant_attribution_share": 0 if accepted_count == 0 else variant_count / accepted_count,
        "separate_market_rows": separate_rows,
    }


def fill_band_dates(
    coverage: dict[str, dict[str, dict[str, Any]]],
    start_date,
    end_date,
) -> dict[str, dict[str, dict[str, Any]]]:
    filled: dict[str, dict[str, dict[str, Any]]] = {}
    for day in date_keys(start_date, end_date):
        filled[day] = {}
        for band in ConditionBand:
            filled[day][band.value] = coverage.get(day, {}).get(
                band.value,
                {"matched": 0, "priced": False, "variant_id": None},
            )
    return filled


def date_keys(start_date, end_date) -> list[str]:
    values = []
    current = start_date
    while current <= end_date:
        values.append(current.isoformat())
        current += timedelta(days=1)
    return values


def quality_alarms(session, start_date, end_date) -> list[dict[str, Any]]:
    alarms: list[dict[str, Any]] = []
    snapshots = session.scalars(
        select(SnapshotRun).where(
            SnapshotRun.run_date >= start_date,
            SnapshotRun.run_date <= end_date,
        )
    ).all()
    for run in snapshots:
        for slug, counts in (run.bag_counts or {}).items():
            if counts.get("unique", 0) == 0:
                alarms.append({"type": "zero_candidates", "date": run.run_date.isoformat(), "bag_slug": slug})
        aggregate_count = session.scalar(
            select(func.count()).select_from(DailyAggregate).where(
                DailyAggregate.observation_date == run.run_date
            )
        )
        if aggregate_count == 0:
            alarms.append({"type": "missing_aggregates", "date": run.run_date.isoformat()})

    expired_count = session.scalar(
        select(func.count()).select_from(ListingRaw).where(ListingRaw.expires_at < datetime.now(UTC))
    )
    if expired_count:
        alarms.append({"type": "expired_rows_present", "count": int(expired_count)})
    return alarms
