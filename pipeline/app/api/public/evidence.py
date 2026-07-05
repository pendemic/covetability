from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import SessionDep
from app.api.public.bags import get_bag
from app.contract import SourceType
from app.models import CulturalNote, ManualComp

router = APIRouter()


@router.get("/bags/{slug}/auction-records")
def auction_records(
    slug: str,
    session: SessionDep,
    limit: int = Query(default=6, ge=1, le=50),
) -> dict:
    bag = get_bag(session, slug)
    rows = session.scalars(
        select(ManualComp)
        .where(
            ManualComp.bag_model_id == bag.id,
            ManualComp.source_type == SourceType.auction_record,
        )
        .order_by(ManualComp.observed_at.desc(), ManualComp.id.desc())
        .limit(limit)
    ).all()
    return {
        "slug": bag.slug,
        "items": [
            {
                "id": row.id,
                "source": row.source,
                "observed_at": row.observed_at.isoformat() if row.observed_at else None,
                "price": money(row.price),
                "currency": row.currency,
                "condition_band": row.condition_band.value if row.condition_band else None,
                "listing_url": row.listing_url,
                "notes": row.notes,
                "confirmed": row.sold_confirmed,
            }
            for row in rows
        ],
        "total": len(rows),
    }


@router.get("/bags/{slug}/context-notes")
def context_notes(
    slug: str,
    session: SessionDep,
    limit: int = Query(default=5, ge=1, le=20),
) -> dict:
    bag = get_bag(session, slug)
    rows = session.scalars(
        select(CulturalNote)
        .where(CulturalNote.bag_model_id == bag.id)
        .order_by(CulturalNote.note_date.desc(), CulturalNote.id.desc())
        .limit(limit)
    ).all()
    return {
        "slug": bag.slug,
        "items": [
            {
                "id": row.id,
                "note_date": row.note_date.isoformat(),
                "body": row.body,
                "created_by": row.created_by,
            }
            for row in rows
        ],
        "total": len(rows),
    }


def money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
