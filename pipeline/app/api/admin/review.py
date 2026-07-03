from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, or_, select

from app.api.admin.deps import SessionDep
from app.api.admin.labeling import serialize_listing, upsert_gold_label
from app.api.admin.schemas import LabelPayload, ReviewDecisionPayload
from app.contract import GoldLabelOrigin, GoldLabelVerdict, MatchStatus
from app.models import BagModel, ListingRaw

router = APIRouter()


@router.get("/review/queue")
def review_queue(
    session: SessionDep,
    bag: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    query = select(ListingRaw).where(ListingRaw.match_status == MatchStatus.needs_review)
    count_query = select(func.count()).select_from(ListingRaw).where(
        ListingRaw.match_status == MatchStatus.needs_review
    )
    if bag is not None:
        bag_model = session.scalar(select(BagModel).where(BagModel.slug == bag))
        if bag_model is None:
            raise HTTPException(status_code=404, detail="bag not found")
        bag_filter = or_(
            ListingRaw.matched_bag_model_id == bag_model.id,
            ListingRaw.candidate_bag_model_id == bag_model.id,
        )
        query = query.where(bag_filter)
        count_query = count_query.where(bag_filter)

    items = session.scalars(query.order_by(ListingRaw.id).limit(limit).offset(offset)).all()
    total = session.scalar(count_query)
    return {
        "items": [serialize_listing(item) for item in items],
        "total": int(total or 0),
        "limit": limit,
        "offset": offset,
    }


@router.post("/review/{listing_id}/decision")
def review_decision(
    listing_id: int,
    payload: ReviewDecisionPayload,
    session: SessionDep,
) -> dict[str, Any]:
    listing = session.get(ListingRaw, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="listing not found")

    if payload.action == "reject":
        target_bag_id = payload.bag_model_id or listing.matched_bag_model_id or listing.candidate_bag_model_id
        if target_bag_id is None:
            raise HTTPException(status_code=400, detail="review reject requires bag context")
        listing.match_status = MatchStatus.human_rejected
        listing.matched_bag_model_id = None
        listing.matched_variant_id = None
        label = LabelPayload(
            marketplace_item_id=listing.marketplace_item_id,
            bag_model_id=target_bag_id,
            verdict=GoldLabelVerdict.reject,
            rejection_reason=payload.rejection_reason,
        )
    else:
        target_bag_id = payload.bag_model_id or listing.matched_bag_model_id
        if target_bag_id is None:
            raise HTTPException(status_code=400, detail="review approve requires bag context")
        listing.match_status = MatchStatus.human_accepted
        listing.matched_bag_model_id = target_bag_id
        listing.matched_variant_id = payload.variant_id or listing.matched_variant_id
        label = LabelPayload(
            marketplace_item_id=listing.marketplace_item_id,
            bag_model_id=target_bag_id,
            verdict=GoldLabelVerdict.accept,
            accepted_variant_id=listing.matched_variant_id,
        )

    label_id = upsert_gold_label(session, label, origin=GoldLabelOrigin.review_queue)
    session.commit()
    return {"status": "ok", "listing_id": listing_id, "gold_label_id": label_id}
