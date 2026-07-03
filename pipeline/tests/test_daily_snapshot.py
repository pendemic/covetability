from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.contract import ListingEventType
from app.ingestion.fixtures import FixtureSource
from app.ingestion.snapshot import run_snapshot
from app.models import ListingEvent, ListingRaw, SnapshotRun

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "ebay"


def cleanup_snapshot_rows(engine: Engine) -> None:
    with Session(engine) as session:
        session.execute(delete(SnapshotRun))
        session.execute(delete(ListingRaw).where(ListingRaw.marketplace_item_id.like("v1|fx%")))
        session.commit()


def count_fixture_raw(session: Session) -> int:
    return session.scalar(
        select(func.count()).select_from(ListingRaw).where(ListingRaw.marketplace_item_id.like("v1|fx%"))
    )


def count_fixture_events(session: Session, event_type: ListingEventType) -> int:
    return session.scalar(
        select(func.count())
        .select_from(ListingEvent)
        .join(ListingRaw)
        .where(
            ListingRaw.marketplace_item_id.like("v1|fx%"),
            ListingEvent.type == event_type,
        )
    )


def remove_item(fixtures_dir: Path, item_id: str) -> None:
    for path in (fixtures_dir / "search").glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["itemSummaries"] = [
            item for item in payload["itemSummaries"] if item["itemId"] != item_id
        ]
        payload["total"] = len(payload["itemSummaries"])
        payload["limit"] = len(payload["itemSummaries"])
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def change_item_price(fixtures_dir: Path, item_id: str, value: str) -> None:
    for path in (fixtures_dir / "search").glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload["itemSummaries"]:
            if item["itemId"] == item_id:
                item["price"]["value"] = value
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def test_fixture_snapshot_is_idempotent(db_engine: Engine) -> None:
    cleanup_snapshot_rows(db_engine)
    source = FixtureSource(FIXTURES_DIR)

    with Session(db_engine) as session:
        run_snapshot(session, source, as_of=datetime(2026, 7, 2, 12, tzinfo=UTC))
        session.commit()

        raw_count = count_fixture_raw(session)
        new_events = count_fixture_events(session, ListingEventType.new)
        assert raw_count >= 120
        assert new_events == raw_count

        run_snapshot(session, source, as_of=datetime(2026, 7, 2, 15, tzinfo=UTC))
        session.commit()

        assert count_fixture_raw(session) == raw_count
        assert count_fixture_events(session, ListingEventType.new) == new_events
        assert session.scalar(select(func.count()).select_from(SnapshotRun)) == 2

    cleanup_snapshot_rows(db_engine)


def test_missing_listing_gets_ended_on_second_missed_day(tmp_path: Path, db_engine: Engine) -> None:
    cleanup_snapshot_rows(db_engine)
    fixtures = tmp_path / "ebay"
    shutil.copytree(FIXTURES_DIR, fixtures)
    source = FixtureSource(fixtures)
    item_id = "v1|fx-chloe-paddington-001|0"

    with Session(db_engine) as session:
        run_snapshot(session, source, as_of=datetime(2026, 7, 2, 12, tzinfo=UTC))
        session.commit()

        remove_item(fixtures, item_id)
        run_snapshot(session, source, as_of=datetime(2026, 7, 3, 12, tzinfo=UTC))
        session.commit()
        assert count_fixture_events(session, ListingEventType.ended) == 0

        run_snapshot(session, source, as_of=datetime(2026, 7, 4, 12, tzinfo=UTC))
        session.commit()
        assert count_fixture_events(session, ListingEventType.ended) == 1

        run_snapshot(session, source, as_of=datetime(2026, 7, 4, 16, tzinfo=UTC))
        session.commit()
        assert count_fixture_events(session, ListingEventType.ended) == 1

    cleanup_snapshot_rows(db_engine)


def test_price_change_writes_single_repriced_event(tmp_path: Path, db_engine: Engine) -> None:
    cleanup_snapshot_rows(db_engine)
    fixtures = tmp_path / "ebay"
    shutil.copytree(FIXTURES_DIR, fixtures)
    source = FixtureSource(fixtures)
    item_id = "v1|fx-chloe-paddington-001|0"

    with Session(db_engine) as session:
        run_snapshot(session, source, as_of=datetime(2026, 7, 2, 12, tzinfo=UTC))
        session.commit()

        change_item_price(fixtures, item_id, "775.00")
        run_snapshot(session, source, as_of=datetime(2026, 7, 3, 12, tzinfo=UTC))
        session.commit()

        event = session.scalar(
            select(ListingEvent)
            .join(ListingRaw)
            .where(
                ListingRaw.marketplace_item_id == item_id,
                ListingEvent.type == ListingEventType.repriced,
            )
        )
        assert event is not None
        assert event.payload == {"old_price": "725.00", "new_price": "775.00", "currency": "USD"}

        run_snapshot(session, source, as_of=datetime(2026, 7, 3, 16, tzinfo=UTC))
        session.commit()
        assert count_fixture_events(session, ListingEventType.repriced) == 1

    cleanup_snapshot_rows(db_engine)
