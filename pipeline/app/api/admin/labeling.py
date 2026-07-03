from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.api.admin.deps import SessionDep
from app.api.admin.schemas import LabelPayload
from app.contract import GoldLabelOrigin
from app.models import BagModel, GoldLabel, ListingRaw

router = APIRouter()


@router.get("/labeling/queue/next")
def next_labeling_item(
    session: SessionDep,
    bag: str,
    after_id: int | None = None,
) -> dict[str, Any]:
    bag_model = session.scalar(select(BagModel).where(BagModel.slug == bag))
    if bag_model is None:
        raise HTTPException(status_code=404, detail="bag not found")

    labeled_exists = (
        select(GoldLabel.id)
        .where(
            GoldLabel.marketplace_item_id == ListingRaw.marketplace_item_id,
            GoldLabel.bag_model_id == bag_model.id,
        )
        .exists()
    )
    base = select(ListingRaw).where(
        ListingRaw.candidate_bag_model_id == bag_model.id,
        ~labeled_exists,
    )
    if after_id is not None:
        base = base.where(ListingRaw.id > after_id)
    listing = session.scalar(base.order_by(ListingRaw.id).limit(1))
    remaining = session.scalar(
        select(func.count())
        .select_from(ListingRaw)
        .where(
            ListingRaw.candidate_bag_model_id == bag_model.id,
            ~labeled_exists,
        )
    )
    return {
        "item": serialize_listing(listing) if listing is not None else None,
        "remaining": int(remaining or 0),
    }


@router.post("/labels")
def submit_label(session: SessionDep, payload: LabelPayload) -> dict[str, Any]:
    bag_exists = session.scalar(select(BagModel.id).where(BagModel.id == payload.bag_model_id))
    if bag_exists is None:
        raise HTTPException(status_code=404, detail="bag not found")
    label_id = upsert_gold_label(session, payload, origin=GoldLabelOrigin.labeling_ui)
    session.commit()
    return {"id": label_id, "status": "ok"}


def upsert_gold_label(
    session,
    payload: LabelPayload,
    *,
    origin: GoldLabelOrigin,
) -> int:
    listing = session.scalar(
        select(ListingRaw).where(ListingRaw.marketplace_item_id == payload.marketplace_item_id)
    )
    values = {
        "listing_id": listing.id if listing is not None else None,
        "marketplace_item_id": payload.marketplace_item_id,
        "bag_model_id": payload.bag_model_id,
        "verdict": payload.verdict,
        "origin": origin,
        "rejection_reason": payload.rejection_reason,
        "accepted_variant_id": payload.accepted_variant_id,
        "color_family": payload.color_family,
        "condition_band": payload.condition_band,
        "strap_included": payload.strap_included,
        "lock_included": payload.lock_included,
        "key_included": payload.key_included,
        "dustbag_included": payload.dustbag_included,
        "cards_included": payload.cards_included,
        "labeled_by": "admin",
        "labeled_at": datetime.now(UTC),
        "notes": payload.notes,
    }
    statement = (
        insert(GoldLabel)
        .values(**values)
        .on_conflict_do_update(
            constraint="uq_gold_labels_item_bag",
            set_=values,
        )
        .returning(GoldLabel.id)
    )
    return int(session.execute(statement).scalar_one())


def serialize_listing(listing: ListingRaw | None) -> dict[str, Any] | None:
    if listing is None:
        return None
    return {
        "id": listing.id,
        "marketplace_item_id": listing.marketplace_item_id,
        "title": listing.title,
        "price": decimal_to_str(listing.price),
        "currency": listing.currency,
        "shipping_price": decimal_to_str(listing.shipping_price),
        "shipping_currency": listing.shipping_currency,
        "seller_id": listing.seller_id,
        "condition_raw": listing.condition_raw,
        "candidate_query": listing.candidate_query,
        "candidate_bag_model_id": listing.candidate_bag_model_id,
        "item_url": listing.item_url,
        "image_url": image_url(listing.raw_payload),
        "matcher": {
            "status": listing.match_status.value,
            "confidence": float(listing.match_confidence) if listing.match_confidence is not None else None,
            "matched_bag_model_id": listing.matched_bag_model_id,
            "matched_variant_id": listing.matched_variant_id,
            "rule_trace": listing.rule_trace,
        },
    }


def image_url(payload: dict[str, Any]) -> str | None:
    image = payload.get("image")
    if not isinstance(image, dict):
        return None
    value = image.get("imageUrl")
    return value if isinstance(value, str) else None


def decimal_to_str(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None
