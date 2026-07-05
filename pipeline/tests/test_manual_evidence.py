from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.aggregates.compute import compute_aggregates_for_day
from app.contract import ConditionBand, ConditionConfidence, MatchStatus, PriceType, SourceType
from app.main import app
from app.models import BagModel, Brand, CulturalNote, DailyAggregate, ListingRaw, ManualComp
from app.scoring.breadth import marketplace_breadth
from tests.test_admin_api import auth_headers


def cleanup_rows(engine: Engine) -> None:
    with Session(engine) as session:
        bag_ids = select(BagModel.id).where(BagModel.slug.like("evidence-bag-%"))
        session.execute(delete(CulturalNote).where(CulturalNote.bag_model_id.in_(bag_ids)))
        session.execute(delete(ManualComp).where(ManualComp.bag_model_id.in_(bag_ids)))
        session.execute(delete(DailyAggregate).where(DailyAggregate.bag_model_id.in_(bag_ids)))
        session.execute(delete(ListingRaw).where(ListingRaw.source == "evidence-test"))
        session.execute(delete(BagModel).where(BagModel.slug.like("evidence-bag-%")))
        session.execute(delete(Brand).where(Brand.slug.like("evidence-brand-%")))
        session.commit()


@pytest.fixture(autouse=True)
def clean_evidence_rows(db_engine: Engine):
    cleanup_rows(db_engine)
    yield
    cleanup_rows(db_engine)


def create_bag(session: Session) -> BagModel:
    suffix = uuid4().hex
    brand = Brand(slug=f"evidence-brand-{suffix}", name=f"Evidence Brand {suffix}")
    bag = BagModel(
        slug=f"evidence-bag-{suffix}",
        brand=brand,
        model_name="Evidence Bag",
        tracking_since=date(2026, 7, 1),
        initial_queries=[],
    )
    session.add_all([brand, bag])
    session.commit()
    return bag


def valid_comp_payload(bag_id: int, *, source_type: str = "manual", source: str = "vestiaire") -> dict:
    return {
        "bag_model_id": bag_id,
        "source": source,
        "source_type": source_type,
        "observed_at": "2026-07-05T12:00:00Z",
        "entered_by": "operator",
        "listing_url": "https://example.com/evidence",
        "confirmed": source_type == "auction_record",
        "price_type": "realized" if source_type == "auction_record" else "asking",
        "price": "725.00",
        "currency": "USD",
        "shipping_included": True,
        "condition_raw": "Pre-owned - Good",
        "condition_band": "good",
        "condition_confidence": "high",
        "notes": "Phase 6 test row",
    }


def add_manual_comp(
    session: Session,
    bag: BagModel,
    *,
    source: str,
    source_type: SourceType = SourceType.manual,
) -> ManualComp:
    row = ManualComp(
        bag_model_id=bag.id,
        source=source,
        source_type=source_type,
        observed_at=datetime(2026, 7, 5, 12, tzinfo=UTC),
        entered_by="operator",
        listing_url=f"https://example.com/{source}",
        sold_confirmed=source_type == SourceType.auction_record,
        price_type=PriceType.realized if source_type == SourceType.auction_record else PriceType.asking,
        price=Decimal("725.00"),
        currency="USD",
        shipping_included=True,
        condition_raw="Pre-owned - Good",
        condition_band=ConditionBand.good,
        condition_confidence=ConditionConfidence.high,
    )
    session.add(row)
    session.flush()
    return row


def add_listing(session: Session, bag: BagModel) -> ListingRaw:
    row = ListingRaw(
        source="evidence-test",
        source_type=SourceType.api,
        marketplace_item_id=f"evidence-{uuid4().hex}",
        title="Evidence Bag",
        price=Decimal("500.00"),
        currency="USD",
        shipping_price=Decimal("20.00"),
        shipping_currency="USD",
        seller_id="evidence-seller",
        price_type=PriceType.asking,
        match_confidence=Decimal("0.9500"),
        matched_bag_model_id=bag.id,
        match_status=MatchStatus.auto_accepted,
        condition_raw="Pre-owned - Good",
        condition_band=ConditionBand.good,
        condition_confidence=ConditionConfidence.high,
        observed_at=datetime(2026, 7, 5, 12, tzinfo=UTC),
        first_observed=datetime(2026, 7, 5, 12, tzinfo=UTC),
        last_observed=datetime(2026, 7, 5, 12, tzinfo=UTC),
        expires_at=datetime(2026, 10, 3, 12, tzinfo=UTC),
        raw_payload={},
    )
    session.add(row)
    session.flush()
    return row


def test_admin_manual_comp_validation_and_public_auction_records(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        bag = create_bag(session)
        bag_id = bag.id
        slug = bag.slug

    with TestClient(app) as client:
        bad_payload = valid_comp_payload(bag_id)
        bad_payload.pop("condition_band")
        bad = client.post("/admin/evidence/comps", headers=auth_headers(), json=bad_payload)
        good = client.post(
            "/admin/evidence/comps",
            headers=auth_headers(),
            json=valid_comp_payload(bag_id, source_type="auction_record", source="heritage"),
        )
        public = client.get(f"/bags/{slug}/auction-records")

    assert bad.status_code == 422
    assert good.status_code == 200
    assert public.status_code == 200
    assert public.json()["total"] == 1
    assert public.json()["items"][0]["source"] == "heritage"


def test_auction_record_never_enters_aggregate_rows(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        bag = create_bag(session)
        add_manual_comp(session, bag, source="heritage", source_type=SourceType.auction_record)
        compute_aggregates_for_day(session, date(2026, 7, 5), bag_ids={bag.id})
        session.commit()

        row_count = session.scalar(
            select(DailyAggregate.id).where(DailyAggregate.bag_model_id == bag.id).limit(1)
        )

    assert row_count is None


def test_cultural_note_round_trip_to_public_context_endpoint(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        bag = create_bag(session)
        slug = bag.slug

    with TestClient(app) as client:
        created = client.post(
            f"/admin/evidence/bags/{slug}/cultural-notes",
            headers=auth_headers(),
            json={
                "note_date": "2026-07-05",
                "body": "Archive press coverage increased this week.",
                "created_by": "operator",
            },
        )
        public = client.get(f"/bags/{slug}/context-notes")

    assert created.status_code == 200
    assert public.status_code == 200
    assert public.json()["items"][0]["body"] == "Archive press coverage increased this week."


def test_breadth_counts_api_and_manual_sources_but_excludes_auction_records(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        bag = create_bag(session)
        add_listing(session, bag)
        add_manual_comp(session, bag, source="vestiaire", source_type=SourceType.manual)
        add_manual_comp(session, bag, source="heritage", source_type=SourceType.auction_record)
        stale = add_manual_comp(session, bag, source="old-source", source_type=SourceType.manual)
        stale.observed_at = datetime(2026, 5, 1, 12, tzinfo=UTC)
        session.commit()

        result = marketplace_breadth(session, bag.id, date(2026, 7, 5))

    assert result.source_count == 2
    assert result.score == 45
    assert result.sources == ("evidence-test", "vestiaire")
