from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.aggregates.compute import compute_aggregates_for_day
from app.contract import (
    ConditionBand,
    ConditionConfidence,
    MatchStatus,
    PriceType,
    SourceType,
    VariantKind,
)
from app.models import BagModel, BagVariant, Brand, DailyAggregate, ListingRaw


def cleanup_rows(engine: Engine) -> None:
    with Session(engine) as session:
        session.execute(delete(DailyAggregate).where(DailyAggregate.bag_model_id.in_(
            select(BagModel.id).where(BagModel.slug.like("agg-bag-%"))
        )))
        session.execute(delete(ListingRaw).where(ListingRaw.source == "agg-test"))
        session.execute(delete(BagModel).where(BagModel.slug.like("agg-bag-%")))
        session.execute(delete(Brand).where(Brand.slug.like("agg-brand-%")))
        session.commit()


def create_bag(session: Session) -> tuple[BagModel, BagVariant]:
    suffix = uuid4().hex
    brand = Brand(slug=f"agg-brand-{suffix}", name=f"Aggregate Brand {suffix}")
    bag = BagModel(slug=f"agg-bag-{suffix}", brand=brand, model_name="Aggregate Bag")
    variant = BagVariant(
        bag_model=bag,
        name="Separate",
        kind=VariantKind.edition,
        is_separate_market=True,
    )
    session.add_all([brand, bag, variant])
    session.flush()
    return bag, variant


def add_listing(
    session: Session,
    bag: BagModel,
    *,
    day: date,
    price: str,
    band: ConditionBand,
    variant: BagVariant | None = None,
) -> ListingRaw:
    row = ListingRaw(
        source="agg-test",
        source_type=SourceType.api,
        marketplace_item_id=f"agg-{uuid4().hex}",
        title="Aggregate Bag",
        price=Decimal(price),
        currency="USD",
        shipping_price=Decimal("10.00"),
        shipping_currency="USD",
        seller_id=f"seller-{uuid4().hex[:8]}",
        price_type=PriceType.asking,
        match_confidence=Decimal("0.9500"),
        matched_bag_model_id=bag.id,
        matched_variant_id=variant.id if variant else None,
        match_status=MatchStatus.auto_accepted,
        condition_raw=f"Pre-owned - {band.value}",
        condition_band=band,
        condition_confidence=ConditionConfidence.high,
        observed_at=datetime.combine(day, datetime.min.time(), tzinfo=UTC),
        first_observed=datetime.combine(day - timedelta(days=2), datetime.min.time(), tzinfo=UTC),
        last_observed=datetime.combine(day, datetime.min.time(), tzinfo=UTC),
        expires_at=datetime.combine(day + timedelta(days=90), datetime.min.time(), tzinfo=UTC),
        raw_payload={},
    )
    session.add(row)
    session.flush()
    return row


def test_aggregates_keep_separate_market_variant_out_of_model_row(db_engine: Engine) -> None:
    cleanup_rows(db_engine)
    day = date(2026, 7, 10)
    with Session(db_engine) as session:
        bag, variant = create_bag(session)
        for idx in range(6):
            add_listing(session, bag, day=day, price=str(100 + (idx * 10)), band=ConditionBand.good)
        add_listing(session, bag, day=day, price="1000", band=ConditionBand.excellent, variant=variant)

        summary = compute_aggregates_for_day(session, day)
        session.commit()

        model_good = session.scalar(
            select(DailyAggregate).where(
                DailyAggregate.bag_model_id == bag.id,
                DailyAggregate.variant_id.is_(None),
                DailyAggregate.condition_band == ConditionBand.good,
            )
        )
        variant_excellent = session.scalar(
            select(DailyAggregate).where(
                DailyAggregate.bag_model_id == bag.id,
                DailyAggregate.variant_id == variant.id,
                DailyAggregate.condition_band == ConditionBand.excellent,
            )
        )

        assert summary.rows_written == 2
        assert model_good is not None
        assert model_good.matched_listing_count == 6
        assert model_good.median_asking_price == Decimal("125.00")
        assert variant_excellent is not None
        assert variant_excellent.matched_listing_count == 1
        assert variant_excellent.median_asking_price is None

    cleanup_rows(db_engine)


def test_mix_shift_leaves_existing_band_median_unchanged_and_rerun_is_idempotent(db_engine: Engine) -> None:
    cleanup_rows(db_engine)
    day = date(2026, 7, 10)
    with Session(db_engine) as session:
        bag, _variant = create_bag(session)
        for idx in range(6):
            add_listing(session, bag, day=day, price=str(100 + (idx * 10)), band=ConditionBand.good)
            add_listing(session, bag, day=day, price=str(200 + (idx * 10)), band=ConditionBand.very_good)

        compute_aggregates_for_day(session, day)
        first_good = session.scalar(
            select(DailyAggregate.median_asking_price).where(
                DailyAggregate.bag_model_id == bag.id,
                DailyAggregate.condition_band == ConditionBand.good,
            )
        )
        for idx in range(3):
            add_listing(session, bag, day=day, price=str(500 + idx), band=ConditionBand.excellent)
        compute_aggregates_for_day(session, day)
        compute_aggregates_for_day(session, day)
        session.commit()

        second_good = session.scalar(
            select(DailyAggregate.median_asking_price).where(
                DailyAggregate.bag_model_id == bag.id,
                DailyAggregate.condition_band == ConditionBand.good,
            )
        )
        excellent = session.scalar(
            select(DailyAggregate).where(
                DailyAggregate.bag_model_id == bag.id,
                DailyAggregate.condition_band == ConditionBand.excellent,
            )
        )
        row_count = session.scalar(
            select(func.count()).select_from(DailyAggregate).where(DailyAggregate.bag_model_id == bag.id)
        )

        assert first_good == second_good
        assert excellent is not None
        assert excellent.matched_listing_count == 3
        assert excellent.median_asking_price is None
        assert row_count == 3

    cleanup_rows(db_engine)
