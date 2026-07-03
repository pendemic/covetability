from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import DailyAggregate, ListingRaw


@dataclass(frozen=True)
class RetentionSummary:
    candidates: int
    deleted_unmatched: int
    deleted_matched: int
    skipped_unaggregated: int
    dry_run: bool


def expire_raw(
    session: Session,
    *,
    as_of: datetime | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> RetentionSummary:
    """Expire raw API rows under ADR-003.

    Deleting a matched listing cascades its listing events. That is intentional: lifecycle counts become
    durable only after Phase 3 aggregate rows exist.
    """

    now = as_of or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    listings = session.scalars(select(ListingRaw).where(ListingRaw.expires_at < now)).all()
    deleted_unmatched = 0
    deleted_matched = 0
    skipped_unaggregated = 0

    for listing in listings:
        if listing.matched_bag_model_id is None:
            deleted_unmatched += 1
            if not dry_run:
                session.delete(listing)
            continue

        has_covering_aggregate = session.scalar(
            select(DailyAggregate.id).where(
                DailyAggregate.bag_model_id == listing.matched_bag_model_id,
                DailyAggregate.observation_date >= listing.last_observed.date(),
            )
        )
        if force or has_covering_aggregate is not None:
            deleted_matched += 1
            if not dry_run:
                session.delete(listing)
        else:
            skipped_unaggregated += 1

    if not dry_run:
        session.flush()

    return RetentionSummary(
        candidates=len(listings),
        deleted_unmatched=deleted_unmatched,
        deleted_matched=deleted_matched,
        skipped_unaggregated=skipped_unaggregated,
        dry_run=dry_run,
    )


def delete_all_fixture_rows(session: Session) -> None:
    session.execute(delete(ListingRaw).where(ListingRaw.marketplace_item_id.like("v1|fx%")))
