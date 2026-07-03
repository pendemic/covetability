from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.admin.deps import SessionDep
from app.matching.keywords import COLOR_FAMILIES
from app.models import BagModel, GoldLabel, ListingRaw, MatchRun, SnapshotRun

router = APIRouter()


@router.get("/ingestion/summary")
def ingestion_summary(session: SessionDep) -> dict[str, Any]:
    snapshots = session.scalars(select(SnapshotRun).order_by(SnapshotRun.started_at.desc()).limit(10)).all()
    last_match = session.scalar(select(MatchRun).order_by(MatchRun.run_at.desc()).limit(1))
    return {
        "snapshot_runs": [serialize_snapshot(run) for run in snapshots],
        "last_match_run": serialize_match_run(last_match),
        "match_status_by_bag": match_status_by_bag(session),
        "gold_progress": gold_progress(session),
    }


@router.get("/catalog/bags")
def catalog_bags(session: SessionDep) -> dict[str, Any]:
    bags = session.scalars(
        select(BagModel)
        .options(selectinload(BagModel.brand), selectinload(BagModel.variants))
        .order_by(BagModel.slug)
    ).all()
    return {
        "items": [
            {
                "id": bag.id,
                "slug": bag.slug,
                "brand": bag.brand.name,
                "model_name": bag.model_name,
                "variants": [
                    {
                        "id": variant.id,
                        "name": variant.name,
                        "kind": variant.kind.value,
                        "is_separate_market": variant.is_separate_market,
                    }
                    for variant in sorted(bag.variants, key=lambda row: row.name)
                ],
                "color_families": sorted({value for value, _term in COLOR_FAMILIES.get(bag.slug, ())}),
            }
            for bag in bags
        ],
        "total": len(bags),
    }


def match_status_by_bag(session: SessionDep) -> list[dict[str, Any]]:
    rows = session.execute(
        select(BagModel.slug, ListingRaw.match_status, func.count())
        .join(ListingRaw, ListingRaw.candidate_bag_model_id == BagModel.id)
        .group_by(BagModel.slug, ListingRaw.match_status)
        .order_by(BagModel.slug, ListingRaw.match_status)
    ).all()
    grouped: dict[str, dict[str, Any]] = {}
    for slug, status, count in rows:
        grouped.setdefault(slug, {"bag_slug": slug, "statuses": {}})
        grouped[slug]["statuses"][status.value] = int(count)
    return list(grouped.values())


def gold_progress(session: SessionDep) -> list[dict[str, Any]]:
    candidate_rows = dict(
        session.execute(
            select(BagModel.id, func.count(ListingRaw.id))
            .join(ListingRaw, ListingRaw.candidate_bag_model_id == BagModel.id)
            .group_by(BagModel.id)
        ).all()
    )
    label_rows = dict(
        session.execute(
            select(BagModel.id, func.count(GoldLabel.id))
            .join(GoldLabel, GoldLabel.bag_model_id == BagModel.id)
            .group_by(BagModel.id)
        ).all()
    )
    bags = session.scalars(select(BagModel).order_by(BagModel.slug)).all()
    return [
        {
            "bag_slug": bag.slug,
            "candidate_count": int(candidate_rows.get(bag.id, 0)),
            "label_count": int(label_rows.get(bag.id, 0)),
        }
        for bag in bags
    ]


def serialize_snapshot(run: SnapshotRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "run_date": run.run_date.isoformat(),
        "source": run.source,
        "mode": run.mode.value,
        "status": run.status.value,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "bag_counts": run.bag_counts,
        "ended_event_count": run.ended_event_count,
        "error": run.error,
    }


def serialize_match_run(run: MatchRun | None) -> dict[str, Any] | None:
    if run is None:
        return None
    return {
        "id": run.id,
        "run_at": run.run_at.isoformat(),
        "mode": run.mode,
        "matcher_version": run.matcher_version,
        "listings_considered": run.listings_considered,
        "status_counts": run.status_counts,
        "bag_deltas": run.bag_deltas,
        "threshold_exceeded": run.threshold_exceeded,
        "notes": run.notes,
    }
