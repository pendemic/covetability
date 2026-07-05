from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import SessionDep
from app.api.public.schemas import (
    BagDetailResponse,
    BagListItem,
    BagListResponse,
    BrandSummary,
    VariantSummary,
)
from app.models import BagModel

router = APIRouter()


@router.get("/bags", response_model=BagListResponse, response_model_exclude_none=True)
def list_bags(session: SessionDep) -> BagListResponse:
    bags = session.scalars(
        select(BagModel).options(selectinload(BagModel.brand)).order_by(BagModel.slug)
    ).all()
    return BagListResponse(
        items=[
            BagListItem(
                slug=bag.slug,
                model_name=bag.model_name,
                brand=BrandSummary(slug=bag.brand.slug, name=bag.brand.name),
                era=bag.era,
                tracking_since=bag.tracking_since.isoformat() if bag.tracking_since else None,
                editorial_summary=bag.editorial_summary,
            )
            for bag in bags
        ],
        total=len(bags),
    )


@router.get("/bags/{slug}", response_model=BagDetailResponse, response_model_exclude_none=True)
def bag_detail(slug: str, session: SessionDep) -> BagDetailResponse:
    bag = get_bag(session, slug)
    return BagDetailResponse(
        slug=bag.slug,
        model_name=bag.model_name,
        brand=BrandSummary(slug=bag.brand.slug, name=bag.brand.name),
        era=bag.era,
        tracking_since=bag.tracking_since.isoformat() if bag.tracking_since else None,
        editorial={
            "summary": bag.editorial_summary,
            "history": bag.editorial_history,
            "condition_notes": bag.editorial_condition_notes,
        },
        variants=[
            VariantSummary(
                id=variant.id,
                name=variant.name,
                kind=variant.kind,
                attribution_confidence=variant.attribution_confidence,
                is_separate_market=variant.is_separate_market,
            )
            for variant in sorted(bag.variants, key=lambda row: row.name)
        ],
    )


def get_bag(session: SessionDep, slug: str) -> BagModel:
    bag = session.scalar(
        select(BagModel)
        .options(
            selectinload(BagModel.brand),
            selectinload(BagModel.variants),
            selectinload(BagModel.aliases),
            selectinload(BagModel.exclusion_terms),
        )
        .where(BagModel.slug == slug)
    )
    if bag is None:
        raise HTTPException(status_code=404, detail="bag not found")
    return bag
