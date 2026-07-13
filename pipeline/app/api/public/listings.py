from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import SessionDep
from app.api.public.bags import get_bag
from app.api.public.epn import epn_wrap
from app.api.public.market import latest_aggregate_date, money
from app.api.public.schemas import (
    ListingItem,
    ListingsResponse,
    ListingVariant,
    ListingVerdict,
)
from app.contract import (
    ENDED_AFTER_MISSED_DAYS,
    MATCH_AUTO_ACCEPT,
    ConditionBand,
    ConditionConfidence,
)
from app.matching.engine import ACCEPTED_STATUSES
from app.models import BagVariant, DailyAggregate, ListingRaw, SnapshotRun
from app.settings import Settings, get_settings

router = APIRouter()


@router.get(
    "/bags/{slug}/listings",
    response_model=ListingsResponse,
    response_model_exclude_none=True,
)
def bag_listings(
    slug: str,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> ListingsResponse:
    bag = get_bag(session, slug)
    cutoff = active_cutoff(session)
    latest_day = latest_aggregate_date(session, bag.id)
    aggregate_rows = (
        session.scalars(
            select(DailyAggregate).where(
                DailyAggregate.bag_model_id == bag.id,
                DailyAggregate.observation_date == latest_day,
            )
        ).all()
        if latest_day
        else []
    )
    rows_by_key = {
        (row.variant_id, row.condition_band): row
        for row in aggregate_rows
        if row.median_asking_price is not None
    }
    variants = {variant.id: variant for variant in bag.variants}
    separate_variant_ids = {
        variant.id for variant in bag.variants if variant.is_separate_market
    }
    listings = session.scalars(
        select(ListingRaw).where(
            ListingRaw.matched_bag_model_id == bag.id,
            ListingRaw.match_status.in_(ACCEPTED_STATUSES),
            ListingRaw.last_observed >= cutoff,
        )
    ).all()
    settings = get_settings()

    serialized = [
        serialize_listing(listing, variants, separate_variant_ids, rows_by_key, settings)
        for listing in listings
    ]
    serialized.sort(key=listing_sort_key)
    return ListingsResponse(slug=bag.slug, items=serialized[:limit], total=len(serialized))


def active_cutoff(session: SessionDep) -> datetime:
    latest_snapshot = session.scalar(select(func.max(SnapshotRun.run_date)))
    base_date = latest_snapshot or date.today()
    cutoff_date = base_date - timedelta(days=ENDED_AFTER_MISSED_DAYS)
    return datetime.combine(cutoff_date, time.min, tzinfo=UTC)


def serialize_listing(
    listing: ListingRaw,
    variants: dict[int, BagVariant],
    separate_variant_ids: set[int],
    rows_by_key: dict[tuple[int | None, ConditionBand], DailyAggregate],
    settings: Settings,
) -> ListingItem:
    shipping_price = Decimal(listing.shipping_price) if listing.shipping_price is not None else None
    total_price = Decimal(listing.price) + shipping_price if shipping_price is not None else None
    variant = variants.get(listing.matched_variant_id) if listing.matched_variant_id else None
    return ListingItem(
        id=int(listing.id),
        title=listing.title,
        source=listing.source,
        price=money(listing.price) or "0.00",
        currency=listing.currency,
        shipping_price=money(shipping_price),
        total_price=money(total_price),
        condition_band=listing.condition_band,
        condition_confidence=listing.condition_confidence,
        auth_label=listing.auth_label,
        match_confidence=str(Decimal(listing.match_confidence).quantize(Decimal("0.0001")))
        if listing.match_confidence is not None
        else None,
        variant=(
            ListingVariant(
                id=variant.id,
                name=variant.name,
                is_separate_market=variant.is_separate_market,
            )
            if variant
            else None
        ),
        seller_id=listing.seller_id,
        item_location=item_location(listing.raw_payload),
        item_url=epn_wrap(listing.item_url, settings),
        image_url=listing_image(listing.raw_payload),
        last_observed=listing.last_observed.isoformat(),
        verdict=listing_verdict(listing, separate_variant_ids, rows_by_key),
    )


def listing_image(raw_payload: dict | None) -> str | None:
    if not raw_payload:
        return None
    image = raw_payload.get("image")
    if isinstance(image, dict) and image.get("imageUrl"):
        return str(image["imageUrl"])
    thumbnails = raw_payload.get("thumbnailImages")
    if isinstance(thumbnails, list) and thumbnails:
        first = thumbnails[0]
        if isinstance(first, dict) and first.get("imageUrl"):
            return str(first["imageUrl"])
    return None


def item_location(raw_payload: dict | None) -> str | None:
    if not raw_payload:
        return None
    raw_location = raw_payload.get("itemLocation") or raw_payload.get("item_location")
    if raw_location is None:
        return None
    if isinstance(raw_location, str):
        return raw_location
    if not isinstance(raw_location, dict):
        return None
    parts = [
        raw_location.get("city"),
        raw_location.get("stateOrProvince"),
        raw_location.get("postalCode"),
        raw_location.get("country"),
    ]
    return ", ".join(str(part) for part in parts if part) or None


def listing_verdict(
    listing: ListingRaw,
    separate_variant_ids: set[int],
    rows_by_key: dict[tuple[int | None, ConditionBand], DailyAggregate],
) -> ListingVerdict | None:
    if (
        listing.currency != "USD"
        or listing.condition_band is None
        or listing.condition_confidence == ConditionConfidence.indeterminate
        or listing.match_confidence is None
        or Decimal(listing.match_confidence) < Decimal(str(MATCH_AUTO_ACCEPT))
    ):
        return None

    variant_id = listing.matched_variant_id if listing.matched_variant_id in separate_variant_ids else None
    aggregate = rows_by_key.get((variant_id, listing.condition_band))
    if aggregate is None or aggregate.median_asking_price is None:
        return None

    shipping_price = Decimal(listing.shipping_price) if listing.shipping_price is not None else None
    total_price = Decimal(listing.price) + shipping_price if shipping_price is not None else None
    if total_price is not None and aggregate.median_total_price is not None:
        compare_price = total_price
        median_price = Decimal(aggregate.median_total_price)
    else:
        compare_price = Decimal(listing.price)
        median_price = Decimal(aggregate.median_asking_price)

    if median_price == 0:
        return None
    percent = ((compare_price - median_price) / median_price * Decimal("100")).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )
    if percent > Decimal("5"):
        label = "above"
    elif percent < Decimal("-5"):
        label = "below"
    else:
        label = "near"
    return ListingVerdict(percent_diff=str(percent), band=listing.condition_band, label=label)


def listing_sort_key(item: ListingItem) -> tuple[int, Decimal, int]:
    band_index = list(ConditionBand).index(item.condition_band) if item.condition_band else 99
    price = Decimal(item.total_price or item.price)
    return (band_index, price, item.id)
