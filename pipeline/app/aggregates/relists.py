from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contract import PHASH_HAMMING_MAX, RELIST_WINDOW_DAYS, ListingEventType
from app.ingestion.phash import hamming_distance
from app.ingestion.snapshot import write_event
from app.matching.engine import ACCEPTED_STATUSES
from app.matching.normalize import normalize_title
from app.models import BagModel, ListingEvent, ListingRaw


@dataclass
class RelistSummary:
    events_created: int = 0
    by_bag: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class RelistCandidate:
    prior: ListingRaw
    ended_event: ListingEvent
    signals: tuple[str, ...]
    hamming: int | None


def detect_relists(session: Session, run_date: date) -> RelistSummary:
    summary = RelistSummary()
    bag_slug_by_id = {bag.id: bag.slug for bag in session.scalars(select(BagModel)).all()}
    listings = session.scalars(select(ListingRaw).order_by(ListingRaw.id)).all()
    ended_events = session.scalars(
        select(ListingEvent).where(
            ListingEvent.type == ListingEventType.ended,
            ListingEvent.event_date >= run_date - timedelta(days=RELIST_WINDOW_DAYS),
            ListingEvent.event_date <= run_date,
        )
    ).all()
    ended_by_listing: dict[int, list[ListingEvent]] = {}
    for event in ended_events:
        ended_by_listing.setdefault(event.listing_id, []).append(event)

    new_listing_ids = {
        listing_id
        for (listing_id,) in session.execute(
            select(ListingEvent.listing_id).where(
                ListingEvent.type == ListingEventType.new,
                ListingEvent.event_date == run_date,
            )
        )
    }

    for listing in listings:
        if listing.seller_id is None:
            continue
        if listing.id in new_listing_ids:
            candidate = best_prior(listing, listings, ended_by_listing, run_date)
            if candidate is not None:
                created = write_relist_event(session, listing, candidate, run_date)
                add_summary(summary, listing, bag_slug_by_id, created)
        if listing.last_observed.date() == run_date and listing.id in ended_by_listing:
            latest_ended = max(ended_by_listing[listing.id], key=lambda event: event.event_date)
            if has_existing_relist(session, listing.id, latest_ended.event_date):
                continue
            created = write_event(
                session,
                listing.id,
                ListingEventType.possible_relist,
                run_date,
                {
                    "prior_listing_id": listing.id,
                    "prior_item_id": listing.marketplace_item_id,
                    "signals": ["same_item_id"],
                    "days_gap": (run_date - listing.last_observed.date()).days,
                    "hamming": None,
                },
            )
            add_summary(summary, listing, bag_slug_by_id, created)

    session.flush()
    return summary


def best_prior(
    listing: ListingRaw,
    listings: list[ListingRaw],
    ended_by_listing: dict[int, list[ListingEvent]],
    run_date: date,
) -> RelistCandidate | None:
    candidates: list[RelistCandidate] = []
    listing_bag = effective_bag_id(listing)
    listing_title = normalize_title(listing.title).text
    for prior in listings:
        if prior.id == listing.id or prior.id not in ended_by_listing:
            continue
        if prior.source != listing.source or prior.seller_id != listing.seller_id:
            continue
        if effective_bag_id(prior) != listing_bag:
            continue
        days_gap = (run_date - prior.last_observed.date()).days
        if days_gap > RELIST_WINDOW_DAYS:
            continue

        signals: list[str] = []
        hamming: int | None = None
        if normalize_title(prior.title).text == listing_title:
            signals.append("title")
        if prior.image_phash and listing.image_phash:
            hamming = hamming_distance(prior.image_phash, listing.image_phash)
            if hamming <= PHASH_HAMMING_MAX:
                signals.append("phash")
        if not signals:
            continue
        ended_event = max(ended_by_listing[prior.id], key=lambda event: event.event_date)
        candidates.append(
            RelistCandidate(
                prior=prior,
                ended_event=ended_event,
                signals=tuple(signals),
                hamming=hamming,
            )
        )

    if not candidates:
        return None
    candidates.sort(
        key=lambda candidate: (
            "phash" in candidate.signals,
            candidate.prior.last_observed,
        ),
        reverse=True,
    )
    return candidates[0]


def write_relist_event(
    session: Session,
    listing: ListingRaw,
    candidate: RelistCandidate,
    run_date: date,
) -> bool:
    if has_existing_relist(session, listing.id, candidate.ended_event.event_date):
        return False
    return write_event(
        session,
        listing.id,
        ListingEventType.possible_relist,
        run_date,
        {
            "prior_listing_id": candidate.prior.id,
            "prior_item_id": candidate.prior.marketplace_item_id,
            "signals": list(candidate.signals),
            "days_gap": (run_date - candidate.prior.last_observed.date()).days,
            "hamming": candidate.hamming,
        },
    )


def has_existing_relist(session: Session, listing_id: int, since_date: date) -> bool:
    existing = session.scalar(
        select(ListingEvent.id).where(
            ListingEvent.listing_id == listing_id,
            ListingEvent.type == ListingEventType.possible_relist,
            ListingEvent.event_date >= since_date,
        )
    )
    return existing is not None


def effective_bag_id(listing: ListingRaw) -> int | None:
    if listing.match_status in ACCEPTED_STATUSES:
        return listing.matched_bag_model_id
    return listing.candidate_bag_model_id


def add_summary(
    summary: RelistSummary,
    listing: ListingRaw,
    bag_slug_by_id: dict[int, str],
    created: bool,
) -> None:
    if not created:
        return
    summary.events_created += 1
    bag_id = effective_bag_id(listing)
    slug = bag_slug_by_id.get(bag_id, "unknown")
    summary.by_bag[slug] = summary.by_bag.get(slug, 0) + 1
