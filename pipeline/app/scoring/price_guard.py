"""Guarded asking-price series for score v0 (score-spec §3).

The score's price momentum cannot be read directly from ``daily_aggregates``:
the 14-day same-seller repricing rule has to be applied while the per-listing
price history is still known, and the series must survive raw-row expiry. So we
persist a scoring-internal winsorized per-band median in ``score_price_points``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.aggregates.stats import median, quantize_price, winsorize
from app.contract import (
    MIN_LISTINGS_PER_BAND,
    PRICE_REPRICING_MIN_INTERVAL_DAYS,
    ConditionBand,
    ListingEventType,
)
from app.matching.engine import ACCEPTED_STATUSES
from app.models import ListingEvent, ListingRaw, ScorePricePoint


def effective_price(listing: ListingRaw, events: list[ListingEvent], day: date) -> Decimal:
    """Price of ``listing`` as of ``day`` with the 14-day repricing guard applied.

    Reprices by the same seller (i.e. successive reprices of the same listing)
    are counted at most once per 14 days, so a flurry of repricing cannot walk
    the band median upward faster than the guard allows.
    """

    ordered = sorted(events, key=lambda e: e.event_date)
    base: Decimal | None = None
    accepted_price: Decimal | None = None
    last_accepted: date | None = None

    for event in ordered:
        old_price = event.payload.get("old_price")
        new_price = event.payload.get("new_price")
        if base is None and old_price is not None:
            base = Decimal(str(old_price))
        if event.event_date > day:
            break
        within_guard = last_accepted is not None and (event.event_date - last_accepted).days < (
            PRICE_REPRICING_MIN_INTERVAL_DAYS
        )
        if within_guard:
            continue
        if new_price is not None:
            accepted_price = Decimal(str(new_price))
            last_accepted = event.event_date

    if accepted_price is not None:
        return accepted_price
    if base is not None:
        return base
    return Decimal(listing.price)


def build_price_points_for_day(session: Session, bag_id: int, day: date) -> int:
    """Compute and persist guarded per-band medians for one bag/day (idempotent)."""

    session.execute(
        delete(ScorePricePoint).where(
            ScorePricePoint.bag_model_id == bag_id,
            ScorePricePoint.observation_date == day,
        )
    )

    listings = session.scalars(
        select(ListingRaw).where(
            ListingRaw.matched_bag_model_id == bag_id,
            ListingRaw.match_status.in_(ACCEPTED_STATUSES),
            ListingRaw.currency == "USD",
            ListingRaw.condition_band.is_not(None),
        )
    ).all()
    active = [
        listing
        for listing in listings
        if listing.first_observed.date() <= day <= listing.last_observed.date()
    ]
    reprices = _reprices_by_listing(session, [listing.id for listing in active])

    by_band: dict[ConditionBand, list[Decimal]] = {}
    for listing in active:
        price = effective_price(listing, reprices.get(listing.id, []), day)
        by_band.setdefault(listing.condition_band, []).append(price)

    rows = 0
    for band, prices in by_band.items():
        guarded = None
        if len(prices) >= MIN_LISTINGS_PER_BAND:
            guarded = quantize_price(median(winsorize(prices)))
        session.add(
            ScorePricePoint(
                bag_model_id=bag_id,
                condition_band=band,
                observation_date=day,
                guarded_median=guarded,
                listing_count=len(prices),
                trace={"raw_count": len(prices)},
            )
        )
        rows += 1
    session.flush()
    return rows


def _reprices_by_listing(session: Session, listing_ids: list[int]) -> dict[int, list[ListingEvent]]:
    if not listing_ids:
        return {}
    events = session.scalars(
        select(ListingEvent).where(
            ListingEvent.listing_id.in_(listing_ids),
            ListingEvent.type == ListingEventType.repriced,
        )
    ).all()
    grouped: dict[int, list[ListingEvent]] = {}
    for event in events:
        grouped.setdefault(event.listing_id, []).append(event)
    return grouped
