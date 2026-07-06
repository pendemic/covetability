from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import SessionDep
from app.api.public.schemas import (
    BrandSummary,
    DiscoverModule,
    DiscoverResponse,
    DiscoveryBagItem,
)
from app.models import BagModel, DailyAggregate, ScoreDaily

router = APIRouter()


@dataclass(frozen=True)
class BagDiscoveryStats:
    bag: BagModel
    as_of: date | None
    latest_active: int
    baseline_active: int
    active_delta: int
    priced_bands: int
    published_score: float | None


@router.get("/discover", response_model=DiscoverResponse, response_model_exclude_none=True)
def discover(session: SessionDep) -> DiscoverResponse:
    bags = session.scalars(
        select(BagModel).options(selectinload(BagModel.brand)).order_by(BagModel.slug)
    ).all()
    stats = [bag_stats(session, bag) for bag in bags]
    as_of = max((item.as_of for item in stats if item.as_of is not None), default=None)
    return DiscoverResponse(
        as_of_date=as_of.isoformat() if as_of else None,
        modules=[
            featured_module(stats),
            rising_module(stats),
            under_radar_module(stats),
        ],
    )


def bag_stats(session: SessionDep, bag: BagModel) -> BagDiscoveryStats:
    as_of = session.scalar(
        select(func.max(DailyAggregate.observation_date)).where(DailyAggregate.bag_model_id == bag.id)
    )
    published_score = session.scalar(
        select(ScoreDaily.publication_value)
        .where(ScoreDaily.bag_model_id == bag.id, ScoreDaily.published.is_(True))
        .order_by(ScoreDaily.observation_date.desc())
        .limit(1)
    )
    if as_of is None:
        return BagDiscoveryStats(
            bag,
            None,
            0,
            0,
            0,
            0,
            float(published_score) if published_score is not None else None,
        )

    start = as_of - timedelta(days=29)
    rows = session.execute(
        select(
            DailyAggregate.observation_date,
            func.sum(DailyAggregate.active_listing_count),
        )
        .where(
            DailyAggregate.bag_model_id == bag.id,
            DailyAggregate.observation_date >= start,
            DailyAggregate.observation_date <= as_of,
        )
        .group_by(DailyAggregate.observation_date)
        .order_by(DailyAggregate.observation_date)
    ).all()
    latest_active = int(rows[-1][1] or 0) if rows else 0
    baseline_active = int(rows[0][1] or 0) if rows else 0
    priced_bands = int(
        session.scalar(
            select(func.count())
            .select_from(DailyAggregate)
            .where(
                DailyAggregate.bag_model_id == bag.id,
                DailyAggregate.variant_id.is_(None),
                DailyAggregate.observation_date == as_of,
                DailyAggregate.median_asking_price.is_not(None),
            )
        )
        or 0
    )
    return BagDiscoveryStats(
        bag=bag,
        as_of=as_of,
        latest_active=latest_active,
        baseline_active=baseline_active,
        active_delta=latest_active - baseline_active,
        priced_bands=priced_bands,
        published_score=float(published_score) if published_score is not None else None,
    )


def featured_module(stats: list[BagDiscoveryStats]) -> DiscoverModule:
    published = [item for item in stats if item.published_score is not None]
    if published:
        ranked = sorted(published, key=lambda item: item.published_score or 0, reverse=True)
        return DiscoverModule(
            key="featured",
            title="Most Covetable",
            description="Published score leaders from the latest public score track.",
            items=[
                discovery_item(
                    item,
                    metric_label="Published score",
                    metric_value=str(round(item.published_score or 0)),
                    caption=f"{item.priced_bands}/6 priced bands",
                )
                for item in ranked
            ],
        )
    return DiscoverModule(
        key="featured",
        title="Featured",
        description="Pilot bags with public condition-banded tracking.",
        items=[
            discovery_item(
                item,
                metric_label="Tracking",
                metric_value=item.as_of.isoformat() if item.as_of else "Pending",
                caption=f"{item.priced_bands}/6 priced bands" if item.as_of else "No aggregate day yet",
            )
            for item in sorted(stats, key=lambda row: row.bag.slug)
        ],
    )


def rising_module(stats: list[BagDiscoveryStats]) -> DiscoverModule:
    ranked = sorted(stats, key=lambda row: (row.active_delta, row.latest_active), reverse=True)
    return DiscoverModule(
        key="rising_asking_interest",
        title="Rising asking interest",
        description="Largest recent increases in active matched listings.",
        items=[
            discovery_item(
                item,
                metric_label="30-day active change",
                metric_value=signed_int(item.active_delta),
                caption=f"{item.latest_active} active matched listings",
            )
            for item in ranked
        ],
    )


def under_radar_module(stats: list[BagDiscoveryStats]) -> DiscoverModule:
    ranked = sorted(stats, key=lambda row: (row.latest_active, row.priced_bands, row.bag.slug))
    return DiscoverModule(
        key="under_the_radar",
        title="Under the radar",
        description="Low active inventory or limited public range coverage.",
        items=[
            discovery_item(
                item,
                metric_label="Active matched",
                metric_value=str(item.latest_active),
                caption=f"{item.priced_bands}/6 priced bands",
            )
            for item in ranked
        ],
    )


def discovery_item(
    stats: BagDiscoveryStats,
    *,
    metric_label: str,
    metric_value: str,
    caption: str | None = None,
) -> DiscoveryBagItem:
    bag = stats.bag
    return DiscoveryBagItem(
        slug=bag.slug,
        model_name=bag.model_name,
        brand=BrandSummary(slug=bag.brand.slug, name=bag.brand.name),
        tracking_since=bag.tracking_since.isoformat() if bag.tracking_since else None,
        editorial_summary=bag.editorial_summary,
        metric_label=metric_label,
        metric_value=metric_value,
        caption=caption,
        status="ok" if stats.as_of else "insufficient_data",
    )


def signed_int(value: int) -> str:
    return f"+{value}" if value > 0 else str(value)
