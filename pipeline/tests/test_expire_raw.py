from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.contract import ConditionBand, ConditionConfidence, PriceType, SourceType
from app.ingestion.retention import expire_raw
from app.models import BagModel, Brand, DailyAggregate, ListingRaw


def cleanup_retention_rows(engine: Engine) -> None:
    with Session(engine) as session:
        session.execute(delete(ListingRaw).where(ListingRaw.marketplace_item_id.like("v1|fx-retention-%")))
        session.execute(delete(BagModel).where(BagModel.slug.like("retention-bag-%")))
        session.execute(delete(Brand).where(Brand.slug.like("retention-brand-%")))
        session.commit()


@pytest.fixture(autouse=True)
def clean_retention_rows(db_engine: Engine):
    cleanup_retention_rows(db_engine)
    yield
    cleanup_retention_rows(db_engine)


def create_bag(session: Session) -> BagModel:
    suffix = uuid4().hex
    brand = Brand(slug=f"retention-brand-{suffix}", name=f"Retention Brand {suffix}")
    bag = BagModel(
        slug=f"retention-bag-{suffix}",
        brand=brand,
        model_name="Retention Bag",
        tracking_since=date(2026, 7, 1),
        initial_queries=["retention bag"],
    )
    session.add_all([brand, bag])
    session.flush()
    return bag


def create_listing(
    session: Session,
    *,
    item_id: str,
    expires_at: datetime,
    matched_bag_model_id: int | None = None,
) -> ListingRaw:
    listing = ListingRaw(
        source="ebay",
        source_type=SourceType.api,
        marketplace_item_id=item_id,
        title="Retention test listing",
        price=Decimal("500.00"),
        currency="USD",
        price_type=PriceType.asking,
        matched_bag_model_id=matched_bag_model_id,
        condition_raw="Pre-owned",
        condition_band=ConditionBand.good if matched_bag_model_id else None,
        condition_confidence=ConditionConfidence.medium,
        observed_at=expires_at - timedelta(days=91),
        first_observed=expires_at - timedelta(days=91),
        last_observed=expires_at - timedelta(days=91),
        expires_at=expires_at,
        raw_payload={},
    )
    session.add(listing)
    session.flush()
    return listing


def test_expire_raw_deletes_unmatched_rows(db_engine: Engine) -> None:
    now = datetime(2026, 10, 1, 12, tzinfo=UTC)
    with Session(db_engine) as session:
        create_listing(session, item_id=f"v1|fx-retention-unmatched-{uuid4().hex}|0", expires_at=now)
        session.commit()

        summary = expire_raw(session, as_of=now + timedelta(seconds=1))
        session.commit()

        assert summary.deleted_unmatched == 1
        assert (
            session.scalar(
                select(func.count())
                .select_from(ListingRaw)
                .where(ListingRaw.marketplace_item_id.like("v1|fx-retention-unmatched-%"))
            )
            == 0
        )


def test_expire_raw_protects_matched_rows_until_aggregated(db_engine: Engine) -> None:
    now = datetime(2026, 10, 1, 12, tzinfo=UTC)
    with Session(db_engine) as session:
        bag = create_bag(session)
        listing = create_listing(
            session,
            item_id=f"v1|fx-retention-matched-{uuid4().hex}|0",
            expires_at=now,
            matched_bag_model_id=bag.id,
        )
        session.commit()

        summary = expire_raw(session, as_of=now + timedelta(seconds=1))
        session.commit()
        assert summary.skipped_unaggregated == 1
        assert session.get(ListingRaw, listing.id) is not None

        session.add(
            DailyAggregate(
                bag_model_id=bag.id,
                condition_band=ConditionBand.good,
                observation_date=listing.last_observed.date(),
                active_listing_count=8,
                matched_listing_count=8,
                source_count=1,
            )
        )
        session.commit()

        summary = expire_raw(session, as_of=now + timedelta(seconds=1))
        session.commit()
        assert summary.deleted_matched == 1
        assert session.get(ListingRaw, listing.id) is None
        assert session.scalar(select(func.count()).select_from(DailyAggregate)) >= 1


def test_expire_raw_dry_run_deletes_nothing(db_engine: Engine) -> None:
    now = datetime(2026, 10, 1, 12, tzinfo=UTC)
    item_id = f"v1|fx-retention-dry-{uuid4().hex}|0"
    with Session(db_engine) as session:
        listing = create_listing(session, item_id=item_id, expires_at=now)
        session.commit()

        summary = expire_raw(session, as_of=now + timedelta(seconds=1), dry_run=True)
        session.commit()

        assert summary.deleted_unmatched == 1
        assert session.get(ListingRaw, listing.id) is not None
