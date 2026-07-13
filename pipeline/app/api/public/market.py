from __future__ import annotations

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import SessionDep
from app.api.public.bags import get_bag
from app.api.public.schemas import (
    ActivityPoint,
    BandRange,
    HistoryPoint,
    HistoryResponse,
    HistorySeries,
    HistoryVariant,
    MarketResponse,
    MarketTotals,
    MarketVariant,
    ScoreBlock,
    ScoreComponent,
    SearchInterestPoint,
)
from app.contract import (
    AGGREGATE_WINDOW_DAYS,
    PUBLIC_HISTORY_DEFAULT_DAYS,
    PUBLIC_HISTORY_MAX_DAYS,
    ConditionBand,
)
from app.insights.observations import generate_observations
from app.insights.score_observations import generate_score_observations
from app.models import DailyAggregate, ScoreDaily, SearchSignalWeekly

router = APIRouter()


@router.get(
    "/bags/{slug}/market",
    response_model=MarketResponse,
    response_model_exclude_none=True,
)
def bag_market(slug: str, session: SessionDep) -> MarketResponse:
    bag = get_bag(session, slug)
    as_of = latest_aggregate_date(session, bag.id)
    rows = aggregate_rows_for_day(session, bag.id, as_of) if as_of else []
    model_rows = [row for row in rows if row.variant_id is None]
    variant_rows = [row for row in rows if row.variant_id is not None]
    history_rows = recent_aggregate_rows(session, bag.id, as_of) if as_of else []

    bands = build_bands(model_rows)
    separate_variants = [variant for variant in bag.variants if variant.is_separate_market]
    variants = [
        MarketVariant(
            variant_id=variant.id,
            name=variant.name,
            bands=build_bands([row for row in variant_rows if row.variant_id == variant.id]),
        )
        for variant in sorted(separate_variants, key=lambda row: row.name)
    ]

    return MarketResponse(
        slug=bag.slug,
        as_of_date=as_of.isoformat() if as_of else None,
        window_days=AGGREGATE_WINDOW_DAYS,
        tracking_since=bag.tracking_since.isoformat() if bag.tracking_since else None,
        totals=MarketTotals(
            active_matched_listing_count=sum(row.active_listing_count for row in rows),
            bands_with_sufficient_data=sum(1 for band in bands if band.status == "ok"),
        ),
        bands=bands,
        variants=variants,
        score=score_block(session, bag.id, bag.tracking_since.isoformat() if bag.tracking_since else None),
        observations=(
            generate_score_observations(session, bag, as_of)
            if bag.score_published
            else generate_observations(history_rows, as_of)
        )
        if as_of
        else [],
    )


@router.get(
    "/bags/{slug}/history",
    response_model=HistoryResponse,
    response_model_exclude_none=True,
)
def bag_history(
    slug: str,
    session: SessionDep,
    days: int = Query(default=PUBLIC_HISTORY_DEFAULT_DAYS, ge=7, le=PUBLIC_HISTORY_MAX_DAYS),
) -> HistoryResponse:
    bag = get_bag(session, slug)
    as_of = latest_aggregate_date(session, bag.id)
    if as_of is None:
        return HistoryResponse(
            slug=bag.slug,
            tracking_since=bag.tracking_since.isoformat() if bag.tracking_since else None,
            days_of_history=0,
            series=[HistorySeries(band=band, points=[]) for band in ConditionBand],
            activity=[],
            variants=[],
        )

    start_date = as_of - timedelta(days=days - 1)
    rows = session.scalars(
        select(DailyAggregate)
        .where(
            DailyAggregate.bag_model_id == bag.id,
            DailyAggregate.observation_date >= start_date,
            DailyAggregate.observation_date <= as_of,
        )
        .order_by(DailyAggregate.observation_date, DailyAggregate.condition_band)
    ).all()
    model_rows = [row for row in rows if row.variant_id is None]
    variant_rows = [row for row in rows if row.variant_id is not None]
    dates = {row.observation_date for row in rows}
    separate_variants = [variant for variant in bag.variants if variant.is_separate_market]

    return HistoryResponse(
        slug=bag.slug,
        tracking_since=bag.tracking_since.isoformat() if bag.tracking_since else None,
        days_of_history=len(dates),
        series=history_series(model_rows),
        activity=activity_points(model_rows),
        variants=[
            HistoryVariant(
                variant_id=variant.id,
                name=variant.name,
                series=history_series([row for row in variant_rows if row.variant_id == variant.id]),
            )
            for variant in sorted(separate_variants, key=lambda row: row.name)
        ],
        search_interest=search_interest_points(session, bag.id),
    )


def search_interest_points(session: SessionDep, bag_id: int, weeks: int = 26) -> list[SearchInterestPoint]:
    rows = session.scalars(
        select(SearchSignalWeekly)
        .where(
            SearchSignalWeekly.bag_model_id == bag_id,
            SearchSignalWeekly.stitched_value.is_not(None),
        )
        .order_by(SearchSignalWeekly.week_start.desc())
        .limit(weeks)
    ).all()
    return [
        SearchInterestPoint(week_start=row.week_start.isoformat(), value=float(row.stitched_value))
        for row in reversed(rows)
    ]


def latest_aggregate_date(session: SessionDep, bag_id: int):
    return session.scalar(
        select(func.max(DailyAggregate.observation_date)).where(DailyAggregate.bag_model_id == bag_id)
    )


def aggregate_rows_for_day(session: SessionDep, bag_id: int, day):
    return session.scalars(
        select(DailyAggregate).where(
            DailyAggregate.bag_model_id == bag_id,
            DailyAggregate.observation_date == day,
        )
    ).all()


def recent_aggregate_rows(session: SessionDep, bag_id: int, as_of):
    return session.scalars(
        select(DailyAggregate)
        .where(
            DailyAggregate.bag_model_id == bag_id,
            DailyAggregate.observation_date >= as_of - timedelta(days=AGGREGATE_WINDOW_DAYS),
            DailyAggregate.observation_date <= as_of,
        )
        .order_by(DailyAggregate.observation_date)
    ).all()


def build_bands(rows: list[DailyAggregate]) -> list[BandRange]:
    by_band = {row.condition_band: row for row in rows}
    bands: list[BandRange] = []
    for band in ConditionBand:
        row = by_band.get(band)
        if row is None or row.median_asking_price is None:
            bands.append(
                BandRange(
                    band=band,
                    status="insufficient_data",
                    active_listing_count=row.active_listing_count if row else 0,
                    matched_listing_count=row.matched_listing_count if row else 0,
                )
            )
            continue
        bands.append(
            BandRange(
                band=band,
                status="ok",
                active_listing_count=row.active_listing_count,
                matched_listing_count=row.matched_listing_count,
                median_asking_price=money(row.median_asking_price),
                p25_asking_price=money(row.p25_asking_price),
                p75_asking_price=money(row.p75_asking_price),
                median_total_price=money(row.median_total_price),
            )
        )
    return bands


def history_series(rows: list[DailyAggregate]) -> list[HistorySeries]:
    by_band: dict[ConditionBand, list[DailyAggregate]] = {band: [] for band in ConditionBand}
    for row in rows:
        by_band.setdefault(row.condition_band, []).append(row)
    return [
        HistorySeries(
            band=band,
            points=[
                HistoryPoint(
                    date=row.observation_date.isoformat(),
                    median=money(row.median_asking_price),
                    p25=money(row.p25_asking_price),
                    p75=money(row.p75_asking_price),
                    active_listing_count=row.active_listing_count,
                )
                for row in sorted(by_band.get(band, []), key=lambda item: item.observation_date)
            ],
        )
        for band in ConditionBand
    ]


def activity_points(rows: list[DailyAggregate]) -> list[ActivityPoint]:
    by_date: dict[str, dict[str, int]] = {}
    for row in rows:
        item = by_date.setdefault(
            row.observation_date.isoformat(),
            {"active_listing_count": 0, "new_listing_count": 0},
        )
        item["active_listing_count"] += row.active_listing_count
        item["new_listing_count"] += row.new_listing_count
    return [
        ActivityPoint(
            date=day,
            active_listing_count=values["active_listing_count"],
            new_listing_count=values["new_listing_count"],
        )
        for day, values in sorted(by_date.items())
    ]


def score_block(session: SessionDep, bag_id: int, tracking_since: str | None) -> ScoreBlock:
    score = session.scalar(
        select(ScoreDaily)
        .where(ScoreDaily.bag_model_id == bag_id, ScoreDaily.published.is_(True))
        .order_by(ScoreDaily.observation_date.desc())
        .limit(1)
    )
    if score is not None and score.smoothed_score is not None:
        components = (score.component_trace or {}).get("components", {})
        return ScoreBlock(
            status="published",
            tracking_since=tracking_since,
            value=round(float(score.publication_value or score.smoothed_score)),
            classification=score.classification.value if score.classification else None,
            direction=score.direction.value if score.direction else None,
            confidence_label=confidence_label(score.confidence_raw),
            confidence_raw=str(Decimal(score.confidence_raw).quantize(Decimal("0.0001")))
            if score.confidence_raw is not None
            else None,
            components=[
                ScoreComponent(
                    key=key,
                    state="eligible" if component.get("eligible") else "ineligible",
                    eligible=component.get("eligible"),
                    weight_used=decimal_string(component.get("weight")),
                    value=decimal_string(component.get("value")),
                    contribution=decimal_string(component.get("contribution")),
                    reason=component.get("reason"),
                )
                for key, component in components.items()
            ],
        )
    return ScoreBlock(
        status="not_yet_scored",
        tracking_since=tracking_since,
        components=[
            ScoreComponent(key="search", state="insufficient_stable_search_data"),
            ScoreComponent(key="active_inventory", state="not_yet_computed"),
            ScoreComponent(key="asking_price", state="not_yet_computed"),
            ScoreComponent(key="marketplace_breadth", state="not_yet_computed"),
            ScoreComponent(key="listing_turnover_proxy", state="not_yet_computed"),
        ],
    )


def money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def decimal_string(value) -> str | None:
    if value is None:
        return None
    return str(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def confidence_label(value: Decimal | None) -> str | None:
    if value is None:
        return None
    confidence = Decimal(value)
    if confidence < Decimal("0.40"):
        return "Low"
    if confidence < Decimal("0.70"):
        return "Moderate"
    return "High"
