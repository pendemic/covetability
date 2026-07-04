from __future__ import annotations

import argparse
from datetime import date

from app.aggregates.compute import run_daily_aggregates
from app.db import SessionLocal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute daily aggregate rows.")
    parser.add_argument("--date", help="Observation date in YYYY-MM-DD format.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    day = date.fromisoformat(args.date) if args.date else date.today()
    with SessionLocal() as session:
        summary = run_daily_aggregates(session, day)
        session.commit()

    print(
        f"daily aggregates date={day.isoformat()} rows={summary.rows_written} "
        f"relists={summary.relist_events_created}"
    )
    print("bag,rows,relists,unbanded_matched,window_listings")
    for slug, stats in sorted(summary.bag_stats.items()):
        print(
            f"{slug},{stats['rows']},{stats['relists']},"
            f"{stats['unbanded_matched']},{stats['window_listings']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
