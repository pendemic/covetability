from __future__ import annotations

from sqlalchemy import func, select

from app.contract import ListingEventType
from app.db import SessionLocal
from app.models import ListingEvent, ListingRaw, SnapshotRun


def main() -> int:
    with SessionLocal() as session:
        raw_count = session.scalar(
            select(func.count()).select_from(ListingRaw).where(ListingRaw.marketplace_item_id.like("v1|fx%"))
        )
        new_event_count = session.scalar(
            select(func.count())
            .select_from(ListingEvent)
            .join(ListingRaw)
            .where(
                ListingRaw.marketplace_item_id.like("v1|fx%"),
                ListingEvent.type == ListingEventType.new,
            )
        )
        run_count = session.scalar(select(func.count()).select_from(SnapshotRun))

    if raw_count is None or raw_count < 120:
        raise SystemExit(f"Expected at least 120 fixture raw rows, got {raw_count}.")
    if new_event_count != raw_count:
        raise SystemExit(f"Expected new event count to equal raw rows, got {new_event_count}/{raw_count}.")
    if run_count is None or run_count < 1:
        raise SystemExit("Expected at least one snapshot_runs row.")

    print(f"snapshot verified: raw={raw_count} new_events={new_event_count} runs={run_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
