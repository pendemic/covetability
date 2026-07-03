from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, time

from app.contract import SnapshotRunStatus
from app.db import SessionLocal
from app.ingestion.snapshot import run_snapshot
from app.ingestion.source import get_listing_source
from app.settings import get_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the daily listing snapshot.")
    parser.add_argument("--date", help="Snapshot date override in YYYY-MM-DD format.")
    parser.add_argument("--record", help="Directory for recording live Browse responses.")
    return parser.parse_args()


def parse_as_of(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(date.fromisoformat(value), time(hour=12), tzinfo=UTC)


def main() -> int:
    args = parse_args()
    settings = get_settings()
    if args.record:
        settings.ebay_record_dir = args.record
    source = get_listing_source(settings)

    with SessionLocal() as session:
        summary = run_snapshot(session, source, as_of=parse_as_of(args.date))
        session.commit()

    print(f"Snapshot {summary.run_date} source={summary.source} mode={summary.mode} status={summary.status}")
    print("bag,fetched,unique,inserted,updated,repriced,errors")
    for slug, counts in summary.bag_counts.items():
        print(
            f"{slug},{counts['fetched']},{counts['unique']},{counts['inserted']},"
            f"{counts['updated']},{counts['repriced']},{len(counts['query_errors'])}"
        )
    print(f"ended_events,{summary.ended_event_count}")
    return 1 if summary.status == SnapshotRunStatus.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
