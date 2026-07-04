from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.aggregates.relists import RelistSummary, detect_relists
from app.aggregates.stats import price_summary, quantize_confidence, quantize_price
from app.contract import (
    AGGREGATE_WINDOW_DAYS,
    MIN_LISTINGS_PER_BAND,
    ConditionBand,
    ListingEventType,
)
from app.matching.engine import ACCEPTED_STATUSES
from app.models import AggregateRun, BagModel, DailyAggregate, ListingEvent, ListingRaw


@dataclass
class AggregateSummary:
    rows_written: int = 0
    relist_events_created: int = 0
    bag_stats: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class GroupKey:
    bag_model_id: int
    variant_id: int | None
    condition_band: ConditionBand


def run_daily_aggregates(session: Session, day: date) -> AggregateSummary:
    relist_summary = detect_relists(session, day)
    summary = compute_aggregates_for_day(session, day, relist_summary=relist_summary)
    session.add(
        AggregateRun(
            run_at=datetime.now(UTC),
            mode="daily",
            date_from=day,
            date_to=day,
            rows_written=summary.rows_written,
            relist_events_created=summary.relist_events_created,
            bag_stats=summary.bag_stats,
        )
    )
    return summary


def recompute_aggregates(
    session: Session,
    since: date,
    until: date,
    *,
    bag_ids: set[int] | None = None,
    triggered_by: str | None = None,
) -> AggregateSummary:
    total = AggregateSummary()
    current = since
    while current <= until:
        summary = compute_aggregates_for_day(session, current, bag_ids=bag_ids)
        total.rows_written += summary.rows_written
        merge_bag_stats(total.bag_stats, summary.bag_stats)
        current += timedelta(days=1)
    session.add(
        AggregateRun(
            run_at=datetime.now(UTC),
            mode="recompute",
            date_from=since,
            date_to=until,
            rows_written=total.rows_written,
            relist_events_created=0,
            bag_stats=total.bag_stats,
            triggered_by=triggered_by,
        )
    )
    return total


def compute_aggregates_for_day(
    session: Session,
    day: date,
    *,
    bag_ids: set[int] | None = None,
    relist_summary: RelistSummary | None = None,
) -> AggregateSummary:
    relist_summary = relist_summary or RelistSummary()
    bags = session.scalars(
        select(BagModel)
        .options(selectinload(BagModel.variants))
        .order_by(BagModel.slug)
    ).all()
    if bag_ids is not None:
        bags = [bag for bag in bags if bag.id in bag_ids]

    delete_statement = delete(DailyAggregate).where(DailyAggregate.observation_date == day)
    if bag_ids is not None:
        delete_statement = delete_statement.where(DailyAggregate.bag_model_id.in_(bag_ids))
    session.execute(delete_statement)

    listings = session.scalars(
        select(ListingRaw).where(
            ListingRaw.match_status.in_(ACCEPTED_STATUSES),
            ListingRaw.matched_bag_model_id.is_not(None),
            ListingRaw.currency == "USD",
        )
    ).all()
    events_by_listing = events_for_day(session, day)
    future_reprices_by_listing = future_reprices(session, day)
    window_start = day - timedelta(days=AGGREGATE_WINDOW_DAYS - 1)
    rows_written = 0
    bag_stats: dict[str, dict[str, Any]] = {}

    for bag in bags:
        bag_listings = [listing for listing in listings if listing.matched_bag_model_id == bag.id]
        separate_variant_ids = {
            variant.id for variant in bag.variants if variant.is_separate_market
        }
        grouped: dict[GroupKey, list[ListingRaw]] = {}
        unbanded_matched = 0
        window_listing_count = 0
        for listing in bag_listings:
            if not intersects_window(listing, window_start, day):
                continue
            window_listing_count += 1
            if listing.condition_band is None:
                unbanded_matched += 1
                continue
            variant_id = listing.matched_variant_id if listing.matched_variant_id in separate_variant_ids else None
            key = GroupKey(bag.id, variant_id, listing.condition_band)
            grouped.setdefault(key, []).append(listing)

        rows = 0
        for key, group_listings in grouped.items():
            aggregate = build_row(day, key, group_listings, events_by_listing, future_reprices_by_listing)
            session.add(aggregate)
            rows += 1
            rows_written += 1

        bag_stats[bag.slug] = {
            "rows": rows,
            "relists": relist_summary.by_bag.get(bag.slug, 0),
            "unbanded_matched": unbanded_matched,
            "window_listings": window_listing_count,
        }

    session.flush()
    return AggregateSummary(
        rows_written=rows_written,
        relist_events_created=relist_summary.events_created,
        bag_stats=bag_stats,
    )


def build_row(
    day: date,
    key: GroupKey,
    listings: list[ListingRaw],
    events_by_listing: dict[int, list[ListingEvent]],
    future_reprices_by_listing: dict[int, list[ListingEvent]],
) -> DailyAggregate:
    active_count = sum(
        1 for listing in listings if listing.first_observed.date() <= day <= listing.last_observed.date()
    )
    event_counts = {
        ListingEventType.new: 0,
        ListingEventType.ended: 0,
        ListingEventType.possible_relist: 0,
    }
    for listing in listings:
        for event in events_by_listing.get(listing.id, []):
            if event.type in event_counts:
                event_counts[event.type] += 1

    prices = [price_as_of(listing, future_reprices_by_listing) for listing in listings]
    totals = [
        price + Decimal(listing.shipping_price)
        for listing, price in zip(listings, prices, strict=True)
        if listing.shipping_price is not None
    ]
    median_price = p25 = p75 = None
    if len(prices) >= MIN_LISTINGS_PER_BAND:
        median_price, p25, p75 = price_summary(prices)
    median_total = None
    if len(totals) >= MIN_LISTINGS_PER_BAND:
        median_total, _p25_total, _p75_total = price_summary(totals)

    confidences = [
        Decimal(listing.match_confidence) for listing in listings if listing.match_confidence is not None
    ]
    average_confidence = None
    if confidences:
        average_confidence = quantize_confidence(sum(confidences) / Decimal(len(confidences)))

    return DailyAggregate(
        bag_model_id=key.bag_model_id,
        variant_id=key.variant_id,
        condition_band=key.condition_band,
        observation_date=day,
        active_listing_count=active_count,
        new_listing_count=event_counts[ListingEventType.new],
        ended_listing_count=event_counts[ListingEventType.ended],
        possible_relist_count=event_counts[ListingEventType.possible_relist],
        median_asking_price=median_price,
        p25_asking_price=p25,
        p75_asking_price=p75,
        median_total_price=quantize_price(median_total),
        source_count=len({listing.source for listing in listings}),
        matched_listing_count=len(listings),
        average_match_confidence=average_confidence,
    )


def events_for_day(session: Session, day: date) -> dict[int, list[ListingEvent]]:
    events = session.scalars(select(ListingEvent).where(ListingEvent.event_date == day)).all()
    grouped: dict[int, list[ListingEvent]] = {}
    for event in events:
        grouped.setdefault(event.listing_id, []).append(event)
    return grouped


def future_reprices(session: Session, day: date) -> dict[int, list[ListingEvent]]:
    events = session.scalars(
        select(ListingEvent).where(
            ListingEvent.type == ListingEventType.repriced,
            ListingEvent.event_date > day,
        )
    ).all()
    grouped: dict[int, list[ListingEvent]] = {}
    for event in events:
        grouped.setdefault(event.listing_id, []).append(event)
    return grouped


def price_as_of(
    listing: ListingRaw,
    future_reprices_by_listing: dict[int, list[ListingEvent]],
) -> Decimal:
    reprices = future_reprices_by_listing.get(listing.id, [])
    if reprices:
        earliest = min(reprices, key=lambda event: event.event_date)
        old_price = earliest.payload.get("old_price")
        if old_price is not None:
            return Decimal(str(old_price))
    return Decimal(listing.price)


def intersects_window(listing: ListingRaw, window_start: date, day: date) -> bool:
    return listing.first_observed.date() <= day and listing.last_observed.date() >= window_start


def merge_bag_stats(target: dict[str, dict[str, Any]], source: dict[str, dict[str, Any]]) -> None:
    for slug, stats in source.items():
        merged = target.setdefault(
            slug,
            {"rows": 0, "relists": 0, "unbanded_matched": 0, "window_listings": 0},
        )
        for key, value in stats.items():
            merged[key] = merged.get(key, 0) + value
