from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import SessionDep
from app.api.public.schemas import (
    BrandSummary,
    DiscoverModule,
    DiscoverResponse,
    DiscoverTotals,
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
    classification: str | None
    price_now: Decimal | None
    price_delta_pct: float | None
    active_series: list[int]


@router.get("/discover", response_model=DiscoverResponse, response_model_exclude_none=True)
def discover(session: SessionDep) -> DiscoverResponse:
    bags = session.scalars(
        select(BagModel).options(selectinload(BagModel.brand)).order_by(BagModel.slug)
    ).all()
    stats = [bag_stats(session, bag) for bag in bags]
    as_of = max((item.as_of for item in stats if item.as_of is not None), default=None)
    return DiscoverResponse(
        as_of_date=as_of.isoformat() if as_of else None,
        totals=discover_totals(stats),
        modules=[
            featured_module(stats),
            fastest_rising_module(stats),
            rising_price_module(stats),
            emerging_module(stats),
            cooling_module(stats),
            under_radar_module(stats),
        ],
    )


def bag_stats(session: SessionDep, bag: BagModel) -> BagDiscoveryStats:
    as_of = session.scalar(
        select(func.max(DailyAggregate.observation_date)).where(DailyAggregate.bag_model_id == bag.id)
    )
    score_row = session.scalar(
        select(ScoreDaily)
        .where(ScoreDaily.bag_model_id == bag.id, ScoreDaily.published.is_(True))
        .order_by(ScoreDaily.observation_date.desc())
        .limit(1)
    )
    published_score = (
        score_row.publication_value
        if score_row is not None and score_row.smoothed_score is not None
        else None
    )
    classification = (
        score_row.classification.value
        if score_row is not None and score_row.classification is not None
        else None
    )
    if as_of is None:
        return BagDiscoveryStats(
            bag=bag,
            as_of=None,
            latest_active=0,
            baseline_active=0,
            active_delta=0,
            priced_bands=0,
            published_score=float(published_score) if published_score is not None else None,
            classification=classification,
            price_now=None,
            price_delta_pct=None,
            active_series=[],
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

    price_series = model_price_series(session, bag.id, start, as_of)
    price_now = price_series[max(price_series)] if price_series else None
    price_baseline = price_series[min(price_series)] if price_series else None
    price_delta_pct = (
        float((price_now - price_baseline) / price_baseline * 100)
        if price_now is not None and price_baseline not in (None, Decimal(0))
        else None
    )

    return BagDiscoveryStats(
        bag=bag,
        as_of=as_of,
        latest_active=latest_active,
        baseline_active=baseline_active,
        active_delta=latest_active - baseline_active,
        priced_bands=priced_bands,
        published_score=float(published_score) if published_score is not None else None,
        classification=classification,
        price_now=price_now,
        price_delta_pct=price_delta_pct,
        active_series=[int(row[1] or 0) for row in rows],
    )


def discover_totals(stats: list[BagDiscoveryStats]) -> DiscoverTotals:
    published = sorted(item.published_score for item in stats if item.published_score is not None)
    median_score: int | None = None
    if published:
        mid = len(published) // 2
        median_value = (
            published[mid]
            if len(published) % 2
            else (published[mid - 1] + published[mid]) / 2
        )
        median_score = round(median_value)
    surging = sum(1 for item in stats if item.classification in ("surging", "trending"))
    return DiscoverTotals(
        models_tracked=len(stats),
        active_listings=sum(item.latest_active for item in stats),
        median_score=median_score,
        surging_now=surging,
    )


def model_price_series(
    session: SessionDep, bag_id: int, start: date, as_of: date
) -> dict[date, Decimal]:
    """Model-level typical asking per day = median of the variant-null band medians."""
    rows = session.execute(
        select(DailyAggregate.observation_date, DailyAggregate.median_asking_price)
        .where(
            DailyAggregate.bag_model_id == bag_id,
            DailyAggregate.variant_id.is_(None),
            DailyAggregate.observation_date >= start,
            DailyAggregate.observation_date <= as_of,
            DailyAggregate.median_asking_price.is_not(None),
        )
    ).all()
    by_date: dict[date, list[Decimal]] = {}
    for day, price in rows:
        by_date.setdefault(day, []).append(price)
    return {day: Decimal(median(prices)) for day, prices in by_date.items()}


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


def fastest_rising_module(stats: list[BagDiscoveryStats]) -> DiscoverModule:
    rising = [item for item in stats if item.as_of and item.active_delta > 0]
    ranked = sorted(rising, key=lambda row: (row.active_delta, row.latest_active), reverse=True)
    return DiscoverModule(
        key="fastest_rising",
        title="Fastest rising",
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


def rising_price_module(stats: list[BagDiscoveryStats]) -> DiscoverModule:
    rising = [item for item in stats if item.price_delta_pct is not None and item.price_delta_pct > 0]
    ranked = sorted(rising, key=lambda row: row.price_delta_pct or 0, reverse=True)
    return DiscoverModule(
        key="rising_price",
        title="Rising asking price",
        description="Largest 30-day increases in model-level typical asking price.",
        items=[
            discovery_item(
                item,
                metric_label="30-day asking change",
                metric_value=signed_pct(item.price_delta_pct),
                caption=f"${round(item.price_now)} typical asking" if item.price_now is not None else None,
            )
            for item in ranked
        ],
    )


def emerging_module(stats: list[BagDiscoveryStats]) -> DiscoverModule:
    emerging = [item for item in stats if item.as_of and item.bag.tracking_since is not None]
    ranked = sorted(emerging, key=lambda row: row.bag.tracking_since, reverse=True)
    return DiscoverModule(
        key="emerging",
        title="Newly emerging",
        description="Most recently added to public tracking.",
        items=[
            discovery_item(
                item,
                metric_label="First tracked",
                metric_value=item.bag.tracking_since.isoformat() if item.bag.tracking_since else "—",
                caption=f"{item.priced_bands}/6 priced bands",
            )
            for item in ranked
        ],
    )


def cooling_module(stats: list[BagDiscoveryStats]) -> DiscoverModule:
    cooling = [item for item in stats if item.as_of and item.active_delta < 0]
    ranked = sorted(cooling, key=lambda row: (row.active_delta, row.price_delta_pct or 0))
    return DiscoverModule(
        key="cooling",
        title="Cooling",
        description="Recent declines in active listings or typical asking price.",
        items=[
            discovery_item(
                item,
                metric_label="30-day active change",
                metric_value=signed_int(item.active_delta),
                caption=(
                    f"asking {signed_pct(item.price_delta_pct)}"
                    if item.price_delta_pct is not None
                    else f"{item.latest_active} active matched listings"
                ),
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
        sparkline=stats.active_series,
        status="ok" if stats.as_of else "insufficient_data",
    )


def signed_int(value: int) -> str:
    return f"+{value}" if value > 0 else str(value)


def signed_pct(value: float | None) -> str:
    if value is None:
        return "—"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.0f}%"
