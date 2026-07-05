from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contract import SourceType
from app.matching.engine import ACCEPTED_STATUSES
from app.models import ListingRaw, ManualComp

BREADTH_SCORE_BY_SOURCE_COUNT = {
    0: 0,
    1: 20,
    2: 45,
    3: 65,
    4: 80,
}


@dataclass(frozen=True)
class BreadthResult:
    source_count: int
    score: int
    sources: tuple[str, ...]


def marketplace_breadth(session: Session, bag_id: int, as_of: date, *, days: int = 30) -> BreadthResult:
    start = datetime.combine(as_of - timedelta(days=days - 1), time.min, tzinfo=UTC)
    end = datetime.combine(as_of + timedelta(days=1), time.min, tzinfo=UTC)
    sources: set[str] = set()

    listing_sources = session.scalars(
        select(ListingRaw.source).where(
            ListingRaw.matched_bag_model_id == bag_id,
            ListingRaw.match_status.in_(ACCEPTED_STATUSES),
            ListingRaw.last_observed >= start,
            ListingRaw.last_observed < end,
        )
    ).all()
    sources.update(source.strip() for source in listing_sources if source and source.strip())

    manual_sources = session.scalars(
        select(ManualComp.source).where(
            ManualComp.bag_model_id == bag_id,
            ManualComp.source_type != SourceType.auction_record,
            ManualComp.observed_at >= start,
            ManualComp.observed_at < end,
        )
    ).all()
    sources.update(source.strip() for source in manual_sources if source and source.strip())

    count = len(sources)
    return BreadthResult(
        source_count=count,
        score=BREADTH_SCORE_BY_SOURCE_COUNT.get(count, 100),
        sources=tuple(sorted(sources)),
    )
