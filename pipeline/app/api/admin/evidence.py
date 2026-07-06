from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from app.api.admin.deps import SessionDep
from app.contract import ConditionBand, ConditionConfidence, PriceType, SourceType
from app.models import BagModel, CulturalNote, ManualComp

router = APIRouter()


class ManualCompPayload(BaseModel):
    bag_model_id: int
    variant_id: int | None = None
    source: str = Field(min_length=1, max_length=160)
    source_type: SourceType
    observed_at: datetime
    entered_by: str = Field(min_length=1, max_length=160)
    listing_url: str = Field(min_length=1)
    confirmed: bool
    price_type: PriceType
    price: Decimal
    currency: str = Field(min_length=3, max_length=3)
    shipping_included: bool
    condition_raw: str | None = None
    condition_band: ConditionBand
    condition_confidence: ConditionConfidence = ConditionConfidence.high
    notes: str | None = None

    @model_validator(mode="after")
    def check_record_type(self) -> ManualCompPayload:
        if self.source_type == SourceType.api:
            raise ValueError("manual evidence cannot use api source_type")
        if self.source_type == SourceType.auction_record and self.price_type != PriceType.realized:
            raise ValueError("auction records require realized price_type")
        return self


class CulturalNotePayload(BaseModel):
    note_date: str
    body: str = Field(min_length=1)
    created_by: str | None = Field(default=None, max_length=160)


@router.post("/evidence/comps")
def create_comp(payload: ManualCompPayload, session: SessionDep) -> dict[str, Any]:
    bag = session.get(BagModel, payload.bag_model_id)
    if bag is None:
        raise HTTPException(status_code=404, detail="bag not found")
    row = ManualComp(
        bag_model_id=payload.bag_model_id,
        variant_id=payload.variant_id,
        source=payload.source,
        source_type=payload.source_type,
        observed_at=payload.observed_at,
        entered_by=payload.entered_by,
        listing_url=payload.listing_url,
        sold_confirmed=payload.confirmed,
        price_type=payload.price_type,
        price=payload.price,
        currency=payload.currency.upper(),
        shipping_included=payload.shipping_included,
        condition_raw=payload.condition_raw,
        condition_band=payload.condition_band,
        condition_confidence=payload.condition_confidence,
        notes=payload.notes,
    )
    session.add(row)
    session.commit()
    return {"id": row.id}


@router.get("/evidence/bags/{slug}/comps")
def list_comps(
    slug: str,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    bag = get_bag_or_404(session, slug)
    rows = session.scalars(
        select(ManualComp)
        .where(ManualComp.bag_model_id == bag.id)
        .order_by(ManualComp.observed_at.desc(), ManualComp.id.desc())
        .limit(limit)
    ).all()
    return {"items": [serialize_comp(row) for row in rows], "total": len(rows)}


@router.delete("/evidence/comps/{comp_id}")
def delete_comp(comp_id: int, session: SessionDep) -> dict[str, str]:
    row = session.get(ManualComp, comp_id)
    if row is None:
        raise HTTPException(status_code=404, detail="manual evidence not found")
    session.delete(row)
    session.commit()
    return {"status": "deleted"}


@router.get("/evidence/bags/{slug}/cultural-notes")
def list_cultural_notes(
    slug: str,
    session: SessionDep,
    limit: int = Query(default=12, ge=1, le=100),
) -> dict[str, Any]:
    bag = get_bag_or_404(session, slug)
    rows = session.scalars(
        select(CulturalNote)
        .where(CulturalNote.bag_model_id == bag.id)
        .order_by(CulturalNote.note_date.desc(), CulturalNote.id.desc())
        .limit(limit)
    ).all()
    return {"items": [serialize_note(row) for row in rows], "total": len(rows)}


@router.post("/evidence/bags/{slug}/cultural-notes")
def create_cultural_note(
    slug: str,
    payload: CulturalNotePayload,
    session: SessionDep,
) -> dict[str, Any]:
    from datetime import date

    bag = get_bag_or_404(session, slug)
    row = CulturalNote(
        bag_model_id=bag.id,
        note_date=date.fromisoformat(payload.note_date),
        body=payload.body,
        created_by=payload.created_by,
    )
    session.add(row)
    session.commit()
    return {"id": row.id}


@router.delete("/evidence/cultural-notes/{note_id}")
def delete_cultural_note(note_id: int, session: SessionDep) -> dict[str, str]:
    row = session.get(CulturalNote, note_id)
    if row is None:
        raise HTTPException(status_code=404, detail="cultural note not found")
    session.delete(row)
    session.commit()
    return {"status": "deleted"}


def get_bag_or_404(session: SessionDep, slug: str) -> BagModel:
    bag = session.scalar(select(BagModel).where(BagModel.slug == slug))
    if bag is None:
        raise HTTPException(status_code=404, detail="bag not found")
    return bag


def serialize_comp(row: ManualComp) -> dict[str, Any]:
    return {
        "id": row.id,
        "bag_model_id": row.bag_model_id,
        "variant_id": row.variant_id,
        "source": row.source,
        "source_type": row.source_type.value,
        "observed_at": row.observed_at.isoformat() if row.observed_at else None,
        "entered_by": row.entered_by,
        "listing_url": row.listing_url,
        "confirmed": row.sold_confirmed,
        "price_type": row.price_type.value,
        "price": str(row.price),
        "currency": row.currency,
        "shipping_included": row.shipping_included,
        "condition_raw": row.condition_raw,
        "condition_band": row.condition_band.value if row.condition_band else None,
        "condition_confidence": row.condition_confidence.value,
        "notes": row.notes,
    }


def serialize_note(row: CulturalNote) -> dict[str, Any]:
    return {
        "id": row.id,
        "bag_model_id": row.bag_model_id,
        "note_date": row.note_date.isoformat(),
        "body": row.body,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat(),
    }
