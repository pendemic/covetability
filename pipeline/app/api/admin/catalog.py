from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.admin.deps import SessionDep
from app.contract import AliasType, ExclusionScope, RejectionReason, VariantKind
from app.matching.keywords import COLOR_FAMILIES
from app.models import (
    BagAlias,
    BagModel,
    BagVariant,
    Brand,
    DailyAggregate,
    ExclusionTerm,
    ListingRaw,
)

router = APIRouter()


class BrandPayload(BaseModel):
    slug: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)


class BagCreatePayload(BaseModel):
    slug: str = Field(min_length=1, max_length=120)
    brand: BrandPayload
    model_name: str = Field(min_length=1, max_length=180)
    era: str | None = None
    editorial_summary: str | None = None
    editorial_history: str | None = None
    editorial_condition_notes: str | None = None
    expected_range_note: str | None = None
    initial_queries: list[str] = Field(default_factory=list)
    tracking_since: str | None = None


class BagPatchPayload(BaseModel):
    brand: BrandPayload | None = None
    model_name: str | None = Field(default=None, min_length=1, max_length=180)
    era: str | None = None
    editorial_summary: str | None = None
    editorial_history: str | None = None
    editorial_condition_notes: str | None = None
    expected_range_note: str | None = None
    initial_queries: list[str] | None = None
    tracking_since: str | None = None


class AliasPayload(BaseModel):
    alias: str = Field(min_length=1, max_length=240)
    type: AliasType = AliasType.alias


class VariantPayload(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    kind: VariantKind
    attribution_confidence: str | None = None
    is_separate_market: bool = False


class VariantPatchPayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    kind: VariantKind | None = None
    attribution_confidence: str | None = None
    is_separate_market: bool | None = None


class ExclusionPayload(BaseModel):
    term: str = Field(min_length=1, max_length=240)
    reason: RejectionReason
    notes: str | None = None


@router.get("/catalog/bags")
def catalog_bags(session: SessionDep) -> dict[str, Any]:
    bags = session.scalars(
        select(BagModel)
        .options(selectinload(BagModel.brand), selectinload(BagModel.variants))
        .order_by(BagModel.slug)
    ).all()
    return {
        "items": [
            {
                "id": bag.id,
                "slug": bag.slug,
                "brand": bag.brand.name,
                "brand_slug": bag.brand.slug,
                "model_name": bag.model_name,
                "recompute_required": bag.recompute_required,
                "recompute_flagged_at": bag.recompute_flagged_at.isoformat()
                if bag.recompute_flagged_at
                else None,
                "variants": [
                    {
                        "id": variant.id,
                        "name": variant.name,
                        "kind": variant.kind.value,
                        "is_separate_market": variant.is_separate_market,
                    }
                    for variant in sorted(bag.variants, key=lambda row: row.name)
                ],
                "color_families": sorted({value for value, _term in COLOR_FAMILIES.get(bag.slug, ())}),
            }
            for bag in bags
        ],
        "total": len(bags),
    }


@router.post("/catalog/bags")
def create_bag(payload: BagCreatePayload, session: SessionDep) -> dict[str, Any]:
    existing = session.scalar(select(BagModel.id).where(BagModel.slug == payload.slug))
    if existing is not None:
        raise HTTPException(status_code=409, detail="bag slug already exists")
    brand = upsert_brand(session, payload.brand)
    bag = BagModel(slug=payload.slug, brand=brand, model_name=payload.model_name)
    apply_bag_payload(bag, payload)
    session.add(bag)
    session.commit()
    return {"id": bag.id, "slug": bag.slug}


@router.get("/catalog/bags/{slug}")
def get_catalog_bag(slug: str, session: SessionDep) -> dict[str, Any]:
    bag = get_bag_or_404(session, slug)
    return serialize_bag_detail(bag, session)


@router.patch("/catalog/bags/{slug}")
def patch_bag(slug: str, payload: BagPatchPayload, session: SessionDep) -> dict[str, Any]:
    bag = get_bag_or_404(session, slug)
    if payload.brand is not None:
        bag.brand = upsert_brand(session, payload.brand)
    data = payload.model_dump(exclude_unset=True, exclude={"brand"})
    for key, value in data.items():
        if key == "tracking_since" and value is not None:
            from datetime import date

            setattr(bag, key, date.fromisoformat(value))
        else:
            setattr(bag, key, value)
    session.commit()
    return serialize_bag_detail(bag, session)


@router.post("/catalog/bags/{slug}/aliases")
def create_alias(slug: str, payload: AliasPayload, session: SessionDep) -> dict[str, Any]:
    bag = get_bag_or_404(session, slug)
    row = BagAlias(bag_model_id=bag.id, alias=payload.alias, type=payload.type)
    session.add(row)
    flag_recompute(session, {bag.id})
    session.commit()
    return {"id": row.id}


@router.delete("/catalog/bags/{slug}/aliases/{alias_id}")
def delete_alias(slug: str, alias_id: int, session: SessionDep) -> dict[str, str]:
    bag = get_bag_or_404(session, slug)
    row = session.get(BagAlias, alias_id)
    if row is None or row.bag_model_id != bag.id:
        raise HTTPException(status_code=404, detail="alias not found")
    session.delete(row)
    flag_recompute(session, {bag.id})
    session.commit()
    return {"status": "deleted"}


@router.post("/catalog/bags/{slug}/variants")
def create_variant(slug: str, payload: VariantPayload, session: SessionDep) -> dict[str, Any]:
    bag = get_bag_or_404(session, slug)
    row = BagVariant(
        bag_model_id=bag.id,
        name=payload.name,
        kind=payload.kind,
        attribution_confidence=payload.attribution_confidence,
        is_separate_market=payload.is_separate_market,
    )
    session.add(row)
    if payload.is_separate_market:
        flag_recompute(session, {bag.id})
    session.commit()
    return {"id": row.id}


@router.patch("/catalog/bags/{slug}/variants/{variant_id}")
def patch_variant(
    slug: str,
    variant_id: int,
    payload: VariantPatchPayload,
    session: SessionDep,
) -> dict[str, Any]:
    bag = get_bag_or_404(session, slug)
    row = session.get(BagVariant, variant_id)
    if row is None or row.bag_model_id != bag.id:
        raise HTTPException(status_code=404, detail="variant not found")
    old_separate = row.is_separate_market
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)
    if old_separate or row.is_separate_market:
        flag_recompute(session, {bag.id})
    session.commit()
    return {"id": row.id}


@router.delete("/catalog/bags/{slug}/variants/{variant_id}")
def delete_variant(slug: str, variant_id: int, session: SessionDep) -> dict[str, str]:
    bag = get_bag_or_404(session, slug)
    row = session.get(BagVariant, variant_id)
    if row is None or row.bag_model_id != bag.id:
        raise HTTPException(status_code=404, detail="variant not found")
    references = session.scalar(
        select(func.count()).select_from(ListingRaw).where(ListingRaw.matched_variant_id == row.id)
    ) or 0
    aggregate_references = session.scalar(
        select(func.count()).select_from(DailyAggregate).where(DailyAggregate.variant_id == row.id)
    ) or 0
    if references or aggregate_references:
        raise HTTPException(status_code=409, detail="variant is referenced by market data")
    should_flag = row.is_separate_market
    session.delete(row)
    if should_flag:
        flag_recompute(session, {bag.id})
    session.commit()
    return {"status": "deleted"}


@router.post("/catalog/bags/{slug}/exclusions")
def create_bag_exclusion(slug: str, payload: ExclusionPayload, session: SessionDep) -> dict[str, Any]:
    bag = get_bag_or_404(session, slug)
    row = ExclusionTerm(
        bag_model_id=bag.id,
        term=payload.term,
        scope=ExclusionScope.bag,
        reason=payload.reason,
        notes=payload.notes,
    )
    session.add(row)
    flag_recompute(session, {bag.id})
    session.commit()
    return {"id": row.id}


@router.delete("/catalog/bags/{slug}/exclusions/{exclusion_id}")
def delete_bag_exclusion(slug: str, exclusion_id: int, session: SessionDep) -> dict[str, str]:
    bag = get_bag_or_404(session, slug)
    row = session.get(ExclusionTerm, exclusion_id)
    if row is None or row.bag_model_id != bag.id:
        raise HTTPException(status_code=404, detail="exclusion not found")
    session.delete(row)
    flag_recompute(session, {bag.id})
    session.commit()
    return {"status": "deleted"}


@router.get("/catalog/exclusions")
def global_exclusions(session: SessionDep) -> dict[str, Any]:
    rows = session.scalars(
        select(ExclusionTerm)
        .where(ExclusionTerm.scope == ExclusionScope.global_scope)
        .order_by(ExclusionTerm.term)
    ).all()
    return {"items": [serialize_exclusion(row) for row in rows], "total": len(rows)}


@router.post("/catalog/exclusions")
def create_global_exclusion(payload: ExclusionPayload, session: SessionDep) -> dict[str, Any]:
    row = ExclusionTerm(
        term=payload.term,
        scope=ExclusionScope.global_scope,
        reason=payload.reason,
        notes=payload.notes,
    )
    session.add(row)
    flag_recompute(session, all_bag_ids(session))
    session.commit()
    return {"id": row.id}


@router.delete("/catalog/exclusions/{exclusion_id}")
def delete_global_exclusion(exclusion_id: int, session: SessionDep) -> dict[str, str]:
    row = session.get(ExclusionTerm, exclusion_id)
    if row is None or row.scope != ExclusionScope.global_scope:
        raise HTTPException(status_code=404, detail="global exclusion not found")
    session.delete(row)
    flag_recompute(session, all_bag_ids(session))
    session.commit()
    return {"status": "deleted"}


def flag_recompute(session: SessionDep, bag_ids: set[int]) -> None:
    now = datetime.now(UTC)
    for bag_id in bag_ids:
        bag = session.get(BagModel, bag_id)
        if bag is not None and not bag.recompute_required:
            bag.recompute_required = True
            bag.recompute_flagged_at = now


def upsert_brand(session: SessionDep, payload: BrandPayload) -> Brand:
    brand = session.scalar(select(Brand).where(Brand.slug == payload.slug))
    if brand is None:
        brand = Brand(slug=payload.slug, name=payload.name)
        session.add(brand)
        session.flush()
    else:
        brand.name = payload.name
    return brand


def apply_bag_payload(bag: BagModel, payload: BagCreatePayload) -> None:
    from datetime import date

    bag.era = payload.era
    bag.editorial_summary = payload.editorial_summary
    bag.editorial_history = payload.editorial_history
    bag.editorial_condition_notes = payload.editorial_condition_notes
    bag.expected_range_note = payload.expected_range_note
    bag.initial_queries = payload.initial_queries
    bag.tracking_since = date.fromisoformat(payload.tracking_since) if payload.tracking_since else None


def get_bag_or_404(session: SessionDep, slug: str) -> BagModel:
    bag = session.scalar(
        select(BagModel)
        .options(
            selectinload(BagModel.brand),
            selectinload(BagModel.aliases),
            selectinload(BagModel.variants),
            selectinload(BagModel.exclusion_terms),
        )
        .where(BagModel.slug == slug)
    )
    if bag is None:
        raise HTTPException(status_code=404, detail="bag not found")
    return bag


def serialize_bag_detail(bag: BagModel, session: SessionDep) -> dict[str, Any]:
    global_rows = session.scalars(
        select(ExclusionTerm)
        .where(ExclusionTerm.scope == ExclusionScope.global_scope)
        .order_by(ExclusionTerm.term)
    ).all()
    return {
        "id": bag.id,
        "slug": bag.slug,
        "brand": {"id": bag.brand.id, "slug": bag.brand.slug, "name": bag.brand.name},
        "model_name": bag.model_name,
        "era": bag.era,
        "editorial_summary": bag.editorial_summary,
        "editorial_history": bag.editorial_history,
        "editorial_condition_notes": bag.editorial_condition_notes,
        "expected_range_note": bag.expected_range_note,
        "initial_queries": bag.initial_queries,
        "tracking_since": bag.tracking_since.isoformat() if bag.tracking_since else None,
        "recompute_required": bag.recompute_required,
        "recompute_flagged_at": bag.recompute_flagged_at.isoformat()
        if bag.recompute_flagged_at
        else None,
        "aliases": [
            {"id": row.id, "alias": row.alias, "type": row.type.value}
            for row in sorted(bag.aliases, key=lambda item: item.alias)
        ],
        "variants": [
            {
                "id": row.id,
                "name": row.name,
                "kind": row.kind.value,
                "attribution_confidence": row.attribution_confidence,
                "is_separate_market": row.is_separate_market,
            }
            for row in sorted(bag.variants, key=lambda item: item.name)
        ],
        "exclusions": [
            serialize_exclusion(row)
            for row in sorted(bag.exclusion_terms, key=lambda item: item.term)
        ],
        "global_exclusions": [serialize_exclusion(row) for row in global_rows],
    }


def serialize_exclusion(row: ExclusionTerm) -> dict[str, Any]:
    return {
        "id": row.id,
        "term": row.term,
        "scope": row.scope.value,
        "reason": row.reason.value,
        "notes": row.notes,
    }


def all_bag_ids(session: SessionDep) -> set[int]:
    return set(session.scalars(select(BagModel.id)).all())
