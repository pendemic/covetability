from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contract import REMATCH_DELTA_THRESHOLD, MatchStatus
from app.matching.matcher import MATCHER_VERSION, CatalogIndex, match_listing
from app.models import BagModel, ListingRaw, MatchRun

PINNED_STATUSES = {MatchStatus.human_accepted, MatchStatus.human_rejected}
ACCEPTED_STATUSES = {MatchStatus.auto_accepted, MatchStatus.human_accepted}


@dataclass(frozen=True)
class MatchingSummary:
    mode: str
    listings_considered: int
    pinned_count: int
    status_counts: dict[str, int]
    bag_deltas: dict[str, dict[str, Any]]
    threshold_exceeded: bool


def apply_matching(
    session: Session,
    index: CatalogIndex | None = None,
    *,
    only_pending: bool = True,
) -> MatchingSummary:
    index = index or CatalogIndex.from_session(session)
    mode = "incremental" if only_pending else "full"
    run_at = datetime.now(UTC)
    id_to_slug = {
        bag.id: bag.slug for bag in session.scalars(select(BagModel).order_by(BagModel.slug)).all()
    }
    before_sets = accepted_sets(session, id_to_slug) if not only_pending else {}

    query = select(ListingRaw).order_by(ListingRaw.id)
    if only_pending:
        query = query.where(ListingRaw.match_status == MatchStatus.pending)
    listings = session.scalars(query).all()

    pinned_count = 0
    status_counts = {status.value: 0 for status in MatchStatus}
    processed_count = 0
    for listing in listings:
        if listing.match_status in PINNED_STATUSES:
            pinned_count += 1
            status_counts[listing.match_status.value] += 1
            continue

        candidate_slug = id_to_slug.get(listing.candidate_bag_model_id)
        result = match_listing(listing.title, index, candidate_bag_slug=candidate_slug)
        listing.match_status = result.status
        listing.rule_trace = result.trace
        listing.matcher_version = MATCHER_VERSION
        listing.matched_at = run_at
        listing.match_confidence = Decimal(str(result.confidence))

        if result.status == MatchStatus.auto_rejected:
            listing.matched_bag_model_id = None
            listing.matched_variant_id = None
        else:
            listing.matched_bag_model_id = index.bag_id_for_slug(result.bag_slug)
            listing.matched_variant_id = index.variant_id_for_name(result.bag_slug, result.variant_name)

        status_counts[result.status.value] += 1
        processed_count += 1

    session.flush()
    bag_deltas = match_deltas(before_sets, accepted_sets(session, id_to_slug)) if not only_pending else {}
    threshold_exceeded = any(
        delta["delta_pct"] > REMATCH_DELTA_THRESHOLD for delta in bag_deltas.values()
    )

    session.add(
        MatchRun(
            run_at=run_at,
            mode=mode,
            matcher_version=MATCHER_VERSION,
            listings_considered=processed_count,
            status_counts={key: value for key, value in status_counts.items() if value},
            bag_deltas=bag_deltas,
            threshold_exceeded=threshold_exceeded,
            notes=f"pinned={pinned_count}" if pinned_count else None,
        )
    )
    return MatchingSummary(
        mode=mode,
        listings_considered=processed_count,
        pinned_count=pinned_count,
        status_counts={key: value for key, value in status_counts.items() if value},
        bag_deltas=bag_deltas,
        threshold_exceeded=threshold_exceeded,
    )


def accepted_sets(session: Session, id_to_slug: dict[int, str]) -> dict[str, set[int]]:
    sets = {slug: set() for slug in id_to_slug.values()}
    rows = session.execute(
        select(ListingRaw.id, ListingRaw.matched_bag_model_id).where(
            ListingRaw.match_status.in_(ACCEPTED_STATUSES),
            ListingRaw.matched_bag_model_id.is_not(None),
        )
    ).all()
    for listing_id, bag_id in rows:
        slug = id_to_slug.get(bag_id)
        if slug is not None:
            sets[slug].add(int(listing_id))
    return sets


def match_deltas(
    before: dict[str, set[int]],
    after: dict[str, set[int]],
) -> dict[str, dict[str, Any]]:
    deltas: dict[str, dict[str, Any]] = {}
    for slug in sorted(set(before) | set(after)):
        before_set = before.get(slug, set())
        after_set = after.get(slug, set())
        added = sorted(after_set - before_set)
        removed = sorted(before_set - after_set)
        delta_pct = round((len(added) + len(removed)) / max(1, len(before_set)), 4)
        deltas[slug] = {
            "before": len(before_set),
            "after": len(after_set),
            "added": added,
            "removed": removed,
            "delta_pct": delta_pct,
        }
    return deltas
