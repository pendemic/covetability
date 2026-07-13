from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, time

from app.contract import SnapshotRunStatus
from app.db import SessionLocal
from app.ingestion.snapshot import SnapshotSummary, run_snapshot
from app.ingestion.source import get_listing_sources
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
    sources = get_listing_sources(settings)
    as_of = parse_as_of(args.date)

    summaries: list[SnapshotSummary] = []
    with SessionLocal() as session:
        for source in sources:
            # Each source is snapshotted independently; listings and ended-events
            # are isolated by source_name, so sources compose cleanly.
            summaries.append(run_snapshot(session, source, as_of=as_of))
        session.commit()

    failed = False
    for summary in summaries:
        print(
            f"Snapshot {summary.run_date} source={summary.source} mode={summary.mode} "
            f"status={summary.status}"
        )
        print("bag,fetched,unique,inserted,updated,repriced,errors")
        for slug, counts in summary.bag_counts.items():
            print(
                f"{slug},{counts['fetched']},{counts['unique']},{counts['inserted']},"
                f"{counts['updated']},{counts['repriced']},{len(counts['query_errors'])}"
            )
        print(f"ended_events,{summary.ended_event_count}")
        failed = failed or summary.status == SnapshotRunStatus.failed
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
