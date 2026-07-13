from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.api.public.epn import epn_wrap
from app.main import app
from app.models import BagModel, ListingRaw
from app.settings import Settings, get_settings
from tests.test_matching_engine import cleanup_fixture_rows
from tests.test_public_api import prepare_public_fixture


def test_catalog_search_matches_brand_model_and_alias(db_engine: Engine) -> None:
    prepare_public_fixture(db_engine)
    with TestClient(app) as client:
        model = client.get("/bags?q=paddington")
        brand = client.get("/bags?q=chloe")
        missing = client.get("/bags?q=not-a-pilot-bag")

    assert model.status_code == 200
    assert brand.status_code == 200
    assert missing.status_code == 200
    assert [item["slug"] for item in model.json()["items"]] == ["chloe-paddington"]
    assert any(item["slug"] == "chloe-paddington" for item in brand.json()["items"])
    assert missing.json()["total"] == 0
    cleanup_fixture_rows(db_engine)


def test_discover_modules_render_without_leaking_internal_scoring(db_engine: Engine) -> None:
    prepare_public_fixture(db_engine)
    with TestClient(app) as client:
        response = client.get("/discover")

    assert response.status_code == 200
    payload = response.json()
    assert payload["totals"]["models_tracked"] >= 1
    assert "active_listings" in payload["totals"]
    assert [module["key"] for module in payload["modules"]] == [
        "featured",
        "fastest_rising",
        "rising_price",
        "emerging",
        "cooling",
        "under_the_radar",
    ]
    # Featured/under-radar/emerging always populate from tracked bags; movement
    # modules (fastest_rising, rising_price, cooling) may legitimately be empty.
    assert payload["modules"][0]["items"]
    assert payload["modules"][-1]["items"]
    # Discover may surface *published* scores (post-launch, per the design), but it
    # must never leak internal/raw scoring machinery.
    dumped = json.dumps(payload).lower()
    for internal in ("raw_score", "smoothed_score", "component_trace", "publication_value", "unscored_reason"):
        assert internal not in dumped
    cleanup_fixture_rows(db_engine)


def test_epn_wrap_is_config_gated_and_ebay_only() -> None:
    raw_url = "https://www.ebay.com/itm/123?hash=abc"
    configured = Settings(epn_campaign_id="5339000000", epn_custom_id="pytest")

    assert epn_wrap(raw_url, Settings()) == raw_url
    assert epn_wrap("https://example.com/item", configured) == "https://example.com/item"

    wrapped = epn_wrap(raw_url, configured)
    assert wrapped is not None
    assert wrapped.startswith("https://rover.ebay.com/rover/")
    assert "campid=5339000000" in wrapped
    assert "customid=pytest" in wrapped
    assert "mpre=https%3A%2F%2Fwww.ebay.com%2Fitm%2F123%3Fhash%3Dabc" in wrapped


def test_listing_payload_includes_affiliate_url_seller_and_location(
    db_engine: Engine, monkeypatch
) -> None:
    prepare_public_fixture(db_engine)
    with Session(db_engine) as session:
        bag = session.scalar(select(BagModel).where(BagModel.slug == "chloe-paddington"))
        assert bag is not None
        listing = session.scalar(
            select(ListingRaw).where(ListingRaw.matched_bag_model_id == bag.id).limit(1)
        )
        assert listing is not None
        listing.raw_payload = {
            "itemLocation": {
                "city": "New York",
                "stateOrProvince": "NY",
                "country": "US",
            }
        }
        listing_id = listing.id
        session.commit()

    monkeypatch.setenv("EPN_CAMPAIGN_ID", "5339000000")
    monkeypatch.setenv("EPN_CUSTOM_ID", "pytest")
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            response = client.get("/bags/chloe-paddington/listings")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    item = next(row for row in response.json()["items"] if row["id"] == listing_id)
    assert item["seller_id"]
    assert item["item_location"] == "New York, NY, US"
    assert item["item_url"].startswith("https://rover.ebay.com/rover/")
    assert "campid=5339000000" in item["item_url"]
    cleanup_fixture_rows(db_engine)
