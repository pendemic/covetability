from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.contract import ConditionBand, GoldLabelVerdict, PriceType, SourceType
from app.models import BagModel, Brand, DailyAggregate, GoldLabel, ManualComp


def cleanup_test_catalog_rows(engine: Engine) -> None:
    with Session(engine) as session:
        session.execute(delete(BagModel).where(BagModel.slug.like("test-bag-%")))
        session.execute(delete(Brand).where(Brand.slug.like("test-brand-%")))
        session.commit()


@pytest.fixture(autouse=True)
def clean_test_catalog_rows(db_engine: Engine):
    cleanup_test_catalog_rows(db_engine)
    yield
    cleanup_test_catalog_rows(db_engine)


def create_test_bag(session: Session) -> BagModel:
    suffix = uuid4().hex
    brand = Brand(slug=f"test-brand-{suffix}", name=f"Test Brand {suffix}")
    bag = BagModel(
        slug=f"test-bag-{suffix}",
        brand=brand,
        model_name="Test Bag",
        tracking_since=date(2026, 7, 1),
        initial_queries=["test bag"],
    )
    session.add_all([brand, bag])
    session.commit()
    return bag


def test_manual_comp_missing_condition_is_rejected(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        bag = create_test_bag(session)
        session.add(
            ManualComp(
                bag_model_id=bag.id,
                source="operator note",
                source_type=SourceType.manual,
                observed_at=datetime.now(UTC),
                price_type=PriceType.asking,
                price=Decimal("500.00"),
                currency="USD",
                condition_band=None,
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()


def test_daily_aggregate_unique_key_treats_null_variant_as_same_bucket(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        bag = create_test_bag(session)
        observation_date = date(2026, 7, 2)
        session.add(
            DailyAggregate(
                bag_model_id=bag.id,
                variant_id=None,
                condition_band=ConditionBand.good,
                observation_date=observation_date,
                active_listing_count=8,
                matched_listing_count=8,
                source_count=1,
            )
        )
        session.commit()

        session.add(
            DailyAggregate(
                bag_model_id=bag.id,
                variant_id=None,
                condition_band=ConditionBand.good,
                observation_date=observation_date,
                active_listing_count=9,
                matched_listing_count=9,
                source_count=1,
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()


def test_gold_label_reject_requires_rejection_reason(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        bag = create_test_bag(session)
        session.add(
            GoldLabel(
                marketplace_item_id=f"test-label-{uuid4().hex}",
                bag_model_id=bag.id,
                verdict=GoldLabelVerdict.reject,
                rejection_reason=None,
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()
