from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.contract import (
    ENDED_AFTER_MISSED_DAYS,
    ListingEventType,
    PriceType,
    SnapshotRunStatus,
    SourceType,
)
from app.ingestion.models import ListingCandidate, to_candidate
from app.ingestion.source import ListingSource
from app.models import BagModel, ListingEvent, ListingRaw, SnapshotRun


@dataclass(frozen=True)
class SnapshotSummary:
    run_date: str
    source: str
    mode: str
    status: SnapshotRunStatus
    bag_counts: dict[str, dict[str, Any]]
    ended_event_count: int
    error: str | None = None


def run_snapshot(
    session: Session,
    source: ListingSource,
    *,
    as_of: datetime | None = None,
) -> SnapshotSummary:
    observed_at = as_of or datetime.now(UTC)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    run_date = observed_at.date()
    started_at = datetime.now(UTC)

    bag_counts: dict[str, dict[str, Any]] = {}
    seen_item_ids: set[str] = set()
    processed_item_ids: set[str] = set()
    status = SnapshotRunStatus.succeeded

    bags = session.scalars(select(BagModel).order_by(BagModel.slug)).all()
    for bag in bags:
        counts: dict[str, Any] = {
            "fetched": 0,
            "unique": 0,
            "inserted": 0,
            "updated": 0,
            "repriced": 0,
            "query_errors": [],
        }
        bag_seen: set[str] = set()

        for query in bag.initial_queries:
            try:
                summaries = list(source.search_active_listings(query))
            except Exception as exc:  # noqa: BLE001 - recorded as partial run metadata
                status = SnapshotRunStatus.partial
                counts["query_errors"].append({"query": query, "error": str(exc)})
                continue

            counts["fetched"] += len(summaries)
            for summary in summaries:
                candidate = to_candidate(summary)
                seen_item_ids.add(candidate.marketplace_item_id)
                bag_seen.add(candidate.marketplace_item_id)
                if candidate.marketplace_item_id in processed_item_ids:
                    continue
                processed_item_ids.add(candidate.marketplace_item_id)
                write_result = upsert_listing(
                    session,
                    source.source_name,
                    candidate,
                    observed_at,
                    candidate_bag_model_id=bag.id,
                    candidate_query=query,
                )
                counts[write_result] += 1

        counts["unique"] = len(bag_seen)
        bag_counts[bag.slug] = counts

    ended_event_count = 0
    if status == SnapshotRunStatus.succeeded:
        ended_event_count = write_ended_events(session, source.source_name, seen_item_ids, observed_at)

    finished_at = datetime.now(UTC)
    session.add(
        SnapshotRun(
            run_date=run_date,
            source=source.source_name,
            mode=source.mode,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            bag_counts=bag_counts,
            ended_event_count=ended_event_count,
        )
    )

    return SnapshotSummary(
        run_date=run_date.isoformat(),
        source=source.source_name,
        mode=source.mode.value,
        status=status,
        bag_counts=bag_counts,
        ended_event_count=ended_event_count,
    )


def upsert_listing(
    session: Session,
    source_name: str,
    candidate: ListingCandidate,
    observed_at: datetime,
    *,
    candidate_bag_model_id: int | None = None,
    candidate_query: str | None = None,
) -> str:
    listing = session.scalar(
        select(ListingRaw).where(
            ListingRaw.source == source_name,
            ListingRaw.marketplace_item_id == candidate.marketplace_item_id,
        )
    )
    expires_at = observed_at + timedelta(days=90)

    if listing is None:
        listing = ListingRaw(
            source=source_name,
            source_type=SourceType.api,
            marketplace_item_id=candidate.marketplace_item_id,
            title=candidate.title,
            price=candidate.price,
            currency=candidate.currency,
            shipping_price=candidate.shipping_price,
            shipping_currency=candidate.shipping_currency,
            shipping_included=candidate.shipping_included,
            seller_id=candidate.seller_id,
            item_url=candidate.item_url,
            price_type=PriceType.asking,
            condition_raw=candidate.condition_raw,
            observed_at=observed_at,
            first_observed=observed_at,
            last_observed=observed_at,
            expires_at=expires_at,
            raw_payload=candidate.raw_payload,
            candidate_bag_model_id=candidate_bag_model_id,
            candidate_query=candidate_query,
        )
        session.add(listing)
        session.flush()
        write_event(session, listing.id, ListingEventType.new, observed_at.date(), {})
        return "inserted"

    old_price = Decimal(listing.price)
    old_currency = listing.currency

    listing.title = candidate.title
    listing.price = candidate.price
    listing.currency = candidate.currency
    listing.shipping_price = candidate.shipping_price
    listing.shipping_currency = candidate.shipping_currency
    listing.shipping_included = candidate.shipping_included
    listing.seller_id = candidate.seller_id
    listing.item_url = candidate.item_url
    listing.condition_raw = candidate.condition_raw
    listing.observed_at = observed_at
    listing.last_observed = observed_at
    listing.expires_at = expires_at
    listing.raw_payload = candidate.raw_payload
    if listing.candidate_bag_model_id is None:
        listing.candidate_bag_model_id = candidate_bag_model_id
    if listing.candidate_query is None:
        listing.candidate_query = candidate_query

    if old_price != candidate.price or old_currency != candidate.currency:
        write_event(
            session,
            listing.id,
            ListingEventType.repriced,
            observed_at.date(),
            {
                "old_price": str(old_price),
                "new_price": str(candidate.price),
                "currency": candidate.currency,
            },
        )
        return "repriced"

    return "updated"


def write_ended_events(
    session: Session,
    source_name: str,
    seen_item_ids: set[str],
    observed_at: datetime,
) -> int:
    run_date = observed_at.date()
    cutoff = observed_at - timedelta(days=ENDED_AFTER_MISSED_DAYS)
    listings = session.scalars(
        select(ListingRaw).where(
            ListingRaw.source == source_name,
            ListingRaw.last_observed <= cutoff,
        )
    ).all()

    ended_count = 0
    for listing in listings:
        if listing.marketplace_item_id in seen_item_ids:
            continue

        existing = session.scalar(
            select(ListingEvent.id).where(
                ListingEvent.listing_id == listing.id,
                ListingEvent.type == ListingEventType.ended,
                ListingEvent.event_date >= listing.last_observed.date(),
            )
        )
        if existing is not None:
            continue

        inserted = write_event(
            session,
            listing.id,
            ListingEventType.ended,
            run_date,
            {
                "last_observed": listing.last_observed.isoformat(),
                "days_absent": (run_date - listing.last_observed.date()).days,
            },
        )
        ended_count += int(inserted)

    return ended_count


def write_event(
    session: Session,
    listing_id: int,
    event_type: ListingEventType,
    event_date,
    payload: dict[str, Any],
) -> bool:
    statement = (
        insert(ListingEvent)
        .values(listing_id=listing_id, type=event_type, event_date=event_date, payload=payload)
        .on_conflict_do_nothing(
            index_elements=["listing_id", "type", "event_date"],
        )
        .returning(ListingEvent.id)
    )
    return session.execute(statement).scalar_one_or_none() is not None
