from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.aggregates.relists import detect_relists
from app.contract import (
    ConditionBand,
    ConditionConfidence,
    ListingEventType,
    MatchStatus,
    PriceType,
    SourceType,
)
from app.ingestion.snapshot import write_event
from app.models import BagModel, Brand, ListingEvent, ListingRaw


def cleanup_rows(engine: Engine) -> None:
    with Session(engine) as session:
        session.execute(delete(ListingRaw).where(ListingRaw.source == "test"))
        session.execute(delete(BagModel).where(BagModel.slug.like("relist-bag-%")))
        session.execute(delete(Brand).where(Brand.slug.like("relist-brand-%")))
        session.commit()


def create_relist_bag(session: Session) -> BagModel:
    suffix = uuid4().hex
    brand = Brand(slug=f"relist-brand-{suffix}", name=f"Relist Brand {suffix}")
    bag = BagModel(slug=f"relist-bag-{suffix}", brand=brand, model_name="Relist Bag")
    session.add_all([brand, bag])
    session.flush()
    return bag


def listing(
    bag: BagModel,
    item_id: str,
    *,
    seller: str,
    title: str,
    first: date,
    last: date,
    phash: str | None = None,
) -> ListingRaw:
    return ListingRaw(
        source="test",
        source_type=SourceType.api,
        marketplace_item_id=item_id,
        title=title,
        price=Decimal("500.00"),
        currency="USD",
        seller_id=seller,
        image_phash=phash,
        price_type=PriceType.asking,
        match_confidence=Decimal("0.9500"),
        matched_bag_model_id=bag.id,
        match_status=MatchStatus.auto_accepted,
        condition_raw="Pre-owned - Good",
        condition_band=ConditionBand.good,
        condition_confidence=ConditionConfidence.high,
        observed_at=datetime.combine(last, datetime.min.time(), tzinfo=UTC),
        first_observed=datetime.combine(first, datetime.min.time(), tzinfo=UTC),
        last_observed=datetime.combine(last, datetime.min.time(), tzinfo=UTC),
        expires_at=datetime.combine(last + timedelta(days=90), datetime.min.time(), tzinfo=UTC),
        raw_payload={},
    )


def test_phash_relist_links_new_listing_to_prior(db_engine: Engine) -> None:
    cleanup_rows(db_engine)
    run_date = date(2026, 7, 10)
    with Session(db_engine) as session:
        bag = create_relist_bag(session)
        prior = listing(
            bag,
            f"relist-prior-{uuid4().hex}",
            seller="same-seller",
            title="Relist Bag black leather",
            first=run_date - timedelta(days=10),
            last=run_date - timedelta(days=2),
            phash="0" * 16,
        )
        new = listing(
            bag,
            f"relist-new-{uuid4().hex}",
            seller="same-seller",
            title="Relist Bag black retitled",
            first=run_date,
            last=run_date,
            phash="0" * 16,
        )
        session.add_all([prior, new])
        session.flush()
        write_event(session, prior.id, ListingEventType.ended, run_date - timedelta(days=1), {})
        write_event(session, new.id, ListingEventType.new, run_date, {})

        summary = detect_relists(session, run_date)
        session.commit()

        event = session.scalar(
            select(ListingEvent).where(
                ListingEvent.listing_id == new.id,
                ListingEvent.type == ListingEventType.possible_relist,
            )
        )
        assert summary.events_created == 1
        assert event is not None
        assert event.payload["prior_listing_id"] == prior.id
        assert event.payload["signals"] == ["phash"]

    cleanup_rows(db_engine)


def test_title_only_relist_fallback_is_idempotent(db_engine: Engine) -> None:
    cleanup_rows(db_engine)
    run_date = date(2026, 7, 10)
    with Session(db_engine) as session:
        bag = create_relist_bag(session)
        prior = listing(
            bag,
            f"relist-prior-{uuid4().hex}",
            seller="same-seller",
            title="Relist Bag exact title",
            first=run_date - timedelta(days=8),
            last=run_date - timedelta(days=2),
        )
        new = listing(
            bag,
            f"relist-new-{uuid4().hex}",
            seller="same-seller",
            title="Relist Bag exact title",
            first=run_date,
            last=run_date,
        )
        session.add_all([prior, new])
        session.flush()
        write_event(session, prior.id, ListingEventType.ended, run_date - timedelta(days=1), {})
        write_event(session, new.id, ListingEventType.new, run_date, {})

        first = detect_relists(session, run_date)
        second = detect_relists(session, run_date)
        session.commit()

        count = session.scalar(
            select(func.count()).select_from(ListingEvent).where(
                ListingEvent.listing_id == new.id,
                ListingEvent.type == ListingEventType.possible_relist,
            )
        )
        assert first.events_created == 1
        assert second.events_created == 0
        assert count == 1

    cleanup_rows(db_engine)


def test_same_id_reappearance_self_links(db_engine: Engine) -> None:
    cleanup_rows(db_engine)
    run_date = date(2026, 7, 10)
    with Session(db_engine) as session:
        bag = create_relist_bag(session)
        row = listing(
            bag,
            f"relist-same-{uuid4().hex}",
            seller="same-seller",
            title="Relist Bag returns",
            first=run_date - timedelta(days=10),
            last=run_date,
        )
        session.add(row)
        session.flush()
        write_event(session, row.id, ListingEventType.ended, run_date - timedelta(days=1), {})

        summary = detect_relists(session, run_date)
        session.commit()

        event = session.scalar(
            select(ListingEvent).where(
                ListingEvent.listing_id == row.id,
                ListingEvent.type == ListingEventType.possible_relist,
            )
        )
        assert summary.events_created == 1
        assert event is not None
        assert event.payload["prior_listing_id"] == row.id

    cleanup_rows(db_engine)
