from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.aggregates.compute import run_daily_aggregates
from app.api.public.schemas import BandRange
from app.contract import ConditionConfidence
from app.main import app
from app.matching.engine import ACCEPTED_STATUSES, apply_matching
from app.models import BagModel, DailyAggregate, ListingRaw
from tests.test_matching_engine import cleanup_fixture_rows, seed_and_snapshot


def prepare_public_fixture(engine: Engine) -> None:
    seed_and_snapshot(engine)
    with Session(engine) as session:
        apply_matching(session)
        run_daily_aggregates(session, date(2026, 7, 2))
        session.commit()


def test_public_bag_routes_do_not_require_auth_and_404(db_engine: Engine) -> None:
    prepare_public_fixture(db_engine)
    with TestClient(app) as client:
        bags = client.get("/bags")
        missing = client.get("/bags/not-a-bag")

    assert bags.status_code == 200
    assert bags.json()["total"] == 5
    assert missing.status_code == 404
    cleanup_fixture_rows(db_engine)


def test_market_schema_has_no_blended_price_and_enforces_insufficient_gate(db_engine: Engine) -> None:
    prepare_public_fixture(db_engine)
    with TestClient(app) as client:
        response = client.get("/bags/chloe-paddington/market")

    assert response.status_code == 200
    payload = response.json()
    assert "median_asking_price" not in payload
    assert len(payload["bands"]) == 6
    assert any(band["status"] == "ok" for band in payload["bands"])
    thin = next(band for band in payload["bands"] if band["status"] == "insufficient_data")
    assert "median_asking_price" not in thin
    assert payload["score"]["status"] == "not_yet_scored"

    with pytest.raises(ValueError):
        BandRange(
            band="good",
            status="insufficient_data",
            active_listing_count=1,
            matched_listing_count=1,
            median_asking_price="100.00",
        )

    cleanup_fixture_rows(db_engine)


def test_public_listing_verdict_eligibility_and_active_filter(db_engine: Engine) -> None:
    prepare_public_fixture(db_engine)
    with Session(db_engine) as session:
        bag = session.scalar(select(BagModel).where(BagModel.slug == "chloe-paddington"))
        assert bag is not None
        priced_row = session.scalar(
            select(DailyAggregate).where(
                DailyAggregate.bag_model_id == bag.id,
                DailyAggregate.variant_id.is_(None),
                DailyAggregate.median_asking_price.is_not(None),
            )
        )
        assert priced_row is not None
        listing = session.scalar(
            select(ListingRaw).where(
                ListingRaw.matched_bag_model_id == bag.id,
                ListingRaw.match_status.in_(ACCEPTED_STATUSES),
                ListingRaw.condition_band == priced_row.condition_band,
            )
        )
        assert listing is not None
        listing_id = listing.id
        session.commit()

    with TestClient(app) as client:
        initial = client.get("/bags/chloe-paddington/listings")
    assert initial.status_code == 200
    initial_item = next(item for item in initial.json()["items"] if item["id"] == listing_id)
    assert initial_item["verdict"] is not None

    with Session(db_engine) as session:
        listing = session.get(ListingRaw, listing_id)
        assert listing is not None
        listing.match_confidence = Decimal("0.8900")
        session.commit()
    with TestClient(app) as client:
        low_confidence = client.get("/bags/chloe-paddington/listings")
    assert next(item for item in low_confidence.json()["items"] if item["id"] == listing_id).get("verdict") is None

    with Session(db_engine) as session:
        listing = session.get(ListingRaw, listing_id)
        assert listing is not None
        listing.match_confidence = Decimal("0.9500")
        listing.condition_confidence = ConditionConfidence.indeterminate
        session.commit()
    with TestClient(app) as client:
        indeterminate = client.get("/bags/chloe-paddington/listings")
    assert next(item for item in indeterminate.json()["items"] if item["id"] == listing_id).get("verdict") is None

    with Session(db_engine) as session:
        listing = session.get(ListingRaw, listing_id)
        assert listing is not None
        listing.condition_confidence = ConditionConfidence.high
        listing.currency = "EUR"
        session.commit()
    with TestClient(app) as client:
        non_usd = client.get("/bags/chloe-paddington/listings")
    assert next(item for item in non_usd.json()["items"] if item["id"] == listing_id).get("verdict") is None

    with Session(db_engine) as session:
        listing = session.get(ListingRaw, listing_id)
        assert listing is not None
        listing.currency = "USD"
        listing.last_observed = listing.last_observed - timedelta(days=10)
        session.commit()
    with TestClient(app) as client:
        inactive = client.get("/bags/chloe-paddington/listings")
    assert all(item["id"] != listing_id for item in inactive.json()["items"])

    cleanup_fixture_rows(db_engine)


def test_public_listings_are_ordered_by_band_then_price(db_engine: Engine) -> None:
    prepare_public_fixture(db_engine)
    with TestClient(app) as client:
        response = client.get("/bags/chloe-paddington/listings")

    items = response.json()["items"]
    band_order = ["new_or_unused", "excellent", "very_good", "good", "fair", "poor"]
    keys = [
        (
            band_order.index(item["condition_band"]) if item.get("condition_band") else 99,
            Decimal(item.get("total_price") or item["price"]),
        )
        for item in items
    ]
    assert keys == sorted(keys)

    cleanup_fixture_rows(db_engine)
