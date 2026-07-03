from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.contract import GoldLabelOrigin, MatchStatus
from app.main import app
from app.matching.engine import apply_matching
from app.models import GoldLabel, ListingRaw
from app.settings import get_settings
from tests.test_matching_engine import cleanup_fixture_rows, seed_and_snapshot


def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_settings().admin_secret}"}


def test_admin_routes_require_shared_secret(db_engine: Engine) -> None:
    with TestClient(app) as client:
        response = client.get("/admin/ingestion/summary")

    assert response.status_code == 401


def test_admin_summary_catalog_and_labeling_round_trip(db_engine: Engine) -> None:
    seed_and_snapshot(db_engine)
    with Session(db_engine) as session:
        apply_matching(session)
        bag = session.scalar(select(ListingRaw.candidate_bag_model_id).where(
            ListingRaw.marketplace_item_id == "v1|fx-chloe-paddington-001|0"
        ))
        session.commit()

    with TestClient(app) as client:
        summary = client.get("/admin/ingestion/summary", headers=auth_headers())
        catalog = client.get("/admin/catalog/bags", headers=auth_headers())
        queue = client.get(
            "/admin/labeling/queue/next?bag=chloe-paddington",
            headers=auth_headers(),
        )

        assert summary.status_code == 200
        assert catalog.status_code == 200
        assert catalog.json()["total"] == 5
        assert queue.status_code == 200
        item = queue.json()["item"]
        assert item is not None

        label_response = client.post(
            "/admin/labels",
            headers=auth_headers(),
            json={
                "marketplace_item_id": item["marketplace_item_id"],
                "bag_model_id": bag,
                "verdict": "accept",
                "color_family": "brown",
            },
        )

    assert label_response.status_code == 200
    with Session(db_engine) as session:
        label = session.scalar(
            select(GoldLabel).where(GoldLabel.marketplace_item_id == item["marketplace_item_id"])
        )
        assert label is not None
        assert label.origin == GoldLabelOrigin.labeling_ui

    cleanup_fixture_rows(db_engine)


def test_admin_review_decision_updates_listing_and_gold_label(db_engine: Engine) -> None:
    seed_and_snapshot(db_engine)
    with Session(db_engine) as session:
        apply_matching(session)
        listing = session.scalar(
            select(ListingRaw).where(ListingRaw.marketplace_item_id == "v1|fx-chloe-paddington-002|0")
        )
        assert listing is not None
        listing.match_status = MatchStatus.needs_review
        session.commit()
        listing_id = listing.id
        bag_id = listing.matched_bag_model_id

    with TestClient(app) as client:
        response = client.post(
            f"/admin/review/{listing_id}/decision",
            headers=auth_headers(),
            json={"action": "approve", "bag_model_id": bag_id},
        )

    assert response.status_code == 200
    with Session(db_engine) as session:
        listing = session.get(ListingRaw, listing_id)
        label = session.scalar(
            select(GoldLabel).where(GoldLabel.marketplace_item_id == "v1|fx-chloe-paddington-002|0")
        )
        assert listing is not None
        assert listing.match_status == MatchStatus.human_accepted
        assert label is not None
        assert label.origin == GoldLabelOrigin.review_queue

    cleanup_fixture_rows(db_engine)
