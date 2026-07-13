from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import SessionDep
from app.api.public.market import money
from app.api.public.schemas import (
    BrandInterestPoint,
    BrandModelItem,
    BrandResponse,
)
from app.models import BagModel, Brand, DailyAggregate, ScoreDaily

router = APIRouter()

HOUSE_WINDOW_DAYS = 90


@dataclass(frozen=True)
class ModelStats:
    bag: BagModel
    as_of: date | None
    active_listings: int
    median_asking: Decimal | None
    sparkline: list[int]
    activity_by_date: dict[date, int]
    score_value: int | None
    score_status: str
    classification: str | None


@router.get("/brands/{slug}", response_model=BrandResponse, response_model_exclude_none=True)
def brand_detail(slug: str, session: SessionDep) -> BrandResponse:
    brand = session.scalar(
        select(Brand)
        .options(selectinload(Brand.bag_models))
        .where(Brand.slug == slug)
    )
    if brand is None:
        raise HTTPException(status_code=404, detail="brand not found")

    stats = [model_stats(session, bag) for bag in sorted(brand.bag_models, key=lambda b: b.slug)]
    tracked = [item for item in stats if item.as_of is not None]
    as_of = max((item.as_of for item in tracked), default=None)

    # House interest = active listings summed across every tracked model per day.
    interest_by_date: dict[date, int] = {}
    for item in stats:
        for day, count in item.activity_by_date.items():
            interest_by_date[day] = interest_by_date.get(day, 0) + count
    interest = [
        BrandInterestPoint(date=day.isoformat(), active_listing_count=count)
        for day, count in sorted(interest_by_date.items())
    ]

    published = [item.score_value for item in stats if item.score_value is not None]
    avg_published = round(sum(published) / len(published)) if published else None

    return BrandResponse(
        slug=brand.slug,
        name=brand.name,
        as_of_date=as_of.isoformat() if as_of else None,
        models_tracked=len(stats),
        active_listings=sum(item.active_listings for item in stats),
        house_momentum_pct=house_momentum(interest),
        average_published_score=avg_published,
        interest=interest,
        models=[
            BrandModelItem(
                slug=item.bag.slug,
                model_name=item.bag.model_name,
                era=item.bag.era,
                active_listings=item.active_listings,
                median_asking_price=money(item.median_asking),
                score_status=item.score_status,  # type: ignore[arg-type]
                score_value=item.score_value,
                classification=item.classification,
                sparkline=item.sparkline,
                status="ok" if item.as_of else "insufficient_data",
            )
            for item in stats
        ],
    )


def model_stats(session: SessionDep, bag: BagModel) -> ModelStats:
    as_of = session.scalar(
        select(func.max(DailyAggregate.observation_date)).where(
            DailyAggregate.bag_model_id == bag.id
        )
    )
    score = session.scalar(
        select(ScoreDaily)
        .where(ScoreDaily.bag_model_id == bag.id, ScoreDaily.published.is_(True))
        .order_by(ScoreDaily.observation_date.desc())
        .limit(1)
    )
    published = score is not None and score.smoothed_score is not None
    score_value = (
        round(float(score.publication_value or score.smoothed_score))
        if published
        else None
    )
    classification = score.classification.value if published and score.classification else None

    if as_of is None:
        return ModelStats(
            bag=bag,
            as_of=None,
            active_listings=0,
            median_asking=None,
            sparkline=[],
            activity_by_date={},
            score_value=score_value,
            score_status="published" if published else "not_yet_scored",
            classification=classification,
        )

    # Model-level (variant_id IS NULL) aggregate rows for the latest day.
    latest_rows = session.scalars(
        select(DailyAggregate).where(
            DailyAggregate.bag_model_id == bag.id,
            DailyAggregate.variant_id.is_(None),
            DailyAggregate.observation_date == as_of,
        )
    ).all()
    active_listings = sum(row.active_listing_count for row in latest_rows)
    priced = [row.median_asking_price for row in latest_rows if row.median_asking_price is not None]
    median_asking = Decimal(median(priced)) if priced else None

    # Active-listing sparkline over the house window (model-level rows only).
    start = as_of - timedelta(days=HOUSE_WINDOW_DAYS - 1)
    window_rows = session.execute(
        select(
            DailyAggregate.observation_date,
            func.sum(DailyAggregate.active_listing_count),
        )
        .where(
            DailyAggregate.bag_model_id == bag.id,
            DailyAggregate.variant_id.is_(None),
            DailyAggregate.observation_date >= start,
            DailyAggregate.observation_date <= as_of,
        )
        .group_by(DailyAggregate.observation_date)
        .order_by(DailyAggregate.observation_date)
    ).all()
    activity_by_date = {row[0]: int(row[1] or 0) for row in window_rows}
    sparkline = [count for _, count in sorted(activity_by_date.items())]

    return ModelStats(
        bag=bag,
        as_of=as_of,
        active_listings=active_listings,
        median_asking=median_asking,
        sparkline=sparkline,
        activity_by_date=activity_by_date,
        score_value=score_value,
        score_status="published" if published else "not_yet_scored",
        classification=classification,
    )


def house_momentum(interest: list[BrandInterestPoint]) -> str | None:
    counts = [point.active_listing_count for point in interest]
    if len(counts) < 2 or counts[0] == 0:
        return None
    change = (counts[-1] - counts[0]) / counts[0] * 100
    sign = "+" if change >= 0 else ""
    return f"{sign}{change:.0f}%"
