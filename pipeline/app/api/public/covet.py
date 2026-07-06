from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.api.deps import SessionDep
from app.api.public.bags import get_bag
from app.models import CovetListWatch

router = APIRouter()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class WatchRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        if not EMAIL_RE.match(email):
            raise ValueError("valid email required")
        return email


@router.post("/bags/{slug}/watch")
def add_watch(slug: str, payload: WatchRequest, session: SessionDep) -> dict:
    bag = get_bag(session, slug)
    stmt = (
        insert(CovetListWatch)
        .values(email=payload.email, bag_model_id=bag.id)
        .on_conflict_do_nothing(index_elements=[CovetListWatch.email, CovetListWatch.bag_model_id])
        .returning(CovetListWatch.id)
    )
    watch_id = session.scalar(stmt)
    if watch_id is None:
        watch_id = session.scalar(
            select(CovetListWatch.id).where(
                CovetListWatch.email == payload.email,
                CovetListWatch.bag_model_id == bag.id,
            )
        )
    session.commit()
    return {"status": "watching", "id": watch_id, "slug": bag.slug}


@router.delete("/bags/{slug}/watch")
def remove_watch(slug: str, session: SessionDep, email: str = Query(...)) -> dict:
    payload = WatchRequest(email=email)
    bag = get_bag(session, slug)
    result = session.execute(
        delete(CovetListWatch).where(
            CovetListWatch.email == payload.email,
            CovetListWatch.bag_model_id == bag.id,
        )
    )
    session.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="watch not found")
    return {"status": "removed", "slug": bag.slug}
