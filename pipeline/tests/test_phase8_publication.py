from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.contract import ScoreClassification, ScoreDirection
from app.main import app
from app.models import BagModel, CovetListWatch, ScoreConfig, ScoreDaily
from jobs.covet_digest import build_digest_payloads
from tests.test_admin_api import auth_headers
from tests.test_matching_engine import cleanup_fixture_rows
from tests.test_public_api import prepare_public_fixture


def cleanup_phase8(engine: Engine) -> None:
    with Session(engine) as session:
        bag_ids = select(BagModel.id).where(BagModel.slug == "chloe-paddington")
        session.execute(delete(CovetListWatch).where(CovetListWatch.bag_model_id.in_(bag_ids)))
        session.execute(delete(ScoreDaily).where(ScoreDaily.bag_model_id.in_(bag_ids)))
        session.execute(delete(ScoreConfig))
        bag = session.scalar(select(BagModel).where(BagModel.slug == "chloe-paddington"))
        if bag is not None:
            bag.score_published = False
            bag.score_published_at = None
        session.commit()
    cleanup_fixture_rows(engine)


def add_score_row(session: Session, bag: BagModel, *, published: bool = False) -> None:
    trace = {
        "scored": True,
        "weights": {
            "search_momentum": 25,
            "active_inventory_momentum": 25,
            "asking_price_momentum": 20,
            "marketplace_breadth": 15,
            "listing_turnover_proxy": 15,
        },
        "eligible": ["search_momentum", "active_inventory_momentum", "asking_price_momentum", "marketplace_breadth"],
        "components": {
            "search_momentum": {
                "value": 75,
                "eligible": True,
                "reason": None,
                "weight": 25,
                "contribution": 18.75,
                "trace": {"bucket": "up"},
            },
            "active_inventory_momentum": {
                "value": 65,
                "eligible": True,
                "reason": None,
                "weight": 25,
                "contribution": 16.25,
                "trace": {},
            },
            "asking_price_momentum": {
                "value": 80,
                "eligible": True,
                "reason": None,
                "weight": 20,
                "contribution": 16,
                "trace": {},
            },
            "marketplace_breadth": {
                "value": 45,
                "eligible": True,
                "reason": None,
                "weight": 15,
                "contribution": 6.75,
                "trace": {"source_count": 2},
            },
            "listing_turnover_proxy": {
                "value": 0,
                "eligible": False,
                "reason": "relist precision unvalidated",
                "weight": 15,
                "contribution": 0,
                "trace": {},
            },
        },
    }
    session.add(
        ScoreDaily(
            bag_model_id=bag.id,
            observation_date=date(2026, 7, 2),
            search_component_value=Decimal("75.00"),
            search_eligible=True,
            search_weight_used=Decimal("25.00"),
            inventory_component_value=Decimal("65.00"),
            inventory_eligible=True,
            inventory_weight_used=Decimal("25.00"),
            price_component_value=Decimal("80.00"),
            price_eligible=True,
            price_weight_used=Decimal("20.00"),
            breadth_component_value=Decimal("45.00"),
            breadth_eligible=True,
            breadth_weight_used=Decimal("15.00"),
            turnover_component_value=Decimal("0.00"),
            turnover_eligible=False,
            turnover_weight_used=Decimal("15.00"),
            raw_score=Decimal("57.75"),
            smoothed_score=Decimal("57.75"),
            publication_value=Decimal("58.00"),
            direction=ScoreDirection.stable,
            confidence_raw=Decimal("0.7200"),
            classification=ScoreClassification.building,
            published=published,
            component_trace=trace,
            notes="fixture publication review",
        )
    )


def test_publish_backfills_public_score_payload(db_engine: Engine) -> None:
    cleanup_phase8(db_engine)
    prepare_public_fixture(db_engine)
    with Session(db_engine) as session:
        bag = session.scalar(select(BagModel).where(BagModel.slug == "chloe-paddington"))
        assert bag is not None
        session.add(
            ScoreConfig(
                id=1,
                search_weight=25,
                decided_at=datetime(2026, 7, 2, tzinfo=UTC),
                rationale="fixture stability decision",
            )
        )
        add_score_row(session, bag)
        session.commit()

    with TestClient(app) as client:
        before = client.get("/bags/chloe-paddington/market")
        readiness = client.get("/admin/score/chloe-paddington/readiness", headers=auth_headers())
        publish = client.post(
            "/admin/score/chloe-paddington/publish",
            headers=auth_headers(),
            json={"force": True, "reason": "fixture publish"},
        )
        after = client.get("/bags/chloe-paddington/market")

    assert before.json()["score"]["status"] == "not_yet_scored"
    assert readiness.status_code == 200
    assert publish.status_code == 200
    score = after.json()["score"]
    assert score["status"] == "published"
    assert score["value"] == 58
    assert score["classification"] == "building"
    assert score["confidence_label"] == "High"
    assert any(component["eligible"] is False for component in score["components"])
    cleanup_phase8(db_engine)


def test_covet_list_watch_is_idempotent_and_digest_does_not_send(db_engine: Engine) -> None:
    cleanup_phase8(db_engine)
    prepare_public_fixture(db_engine)
    with Session(db_engine) as session:
        bag = session.scalar(select(BagModel).where(BagModel.slug == "chloe-paddington"))
        assert bag is not None
        add_score_row(session, bag, published=True)
        session.commit()

    with TestClient(app) as client:
        first = client.post("/bags/chloe-paddington/watch", json={"email": "Reader@Example.com"})
        second = client.post("/bags/chloe-paddington/watch", json={"email": "reader@example.com"})

    assert first.status_code == 200
    assert second.status_code == 200
    with Session(db_engine) as session:
        count = session.scalar(select(CovetListWatch).where(CovetListWatch.email == "reader@example.com"))
        assert count is not None

    payloads = build_digest_payloads()
    digest = next(payload for payload in payloads if payload["email"] == "reader@example.com")
    assert digest["send"] is False
    assert digest["bags"][0]["score"] == 58.0
    cleanup_phase8(db_engine)
