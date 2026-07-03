from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, time

from app.db import SessionLocal
from app.ingestion.retention import expire_raw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Expire raw marketplace rows.")
    parser.add_argument("--date", help="As-of date override in YYYY-MM-DD format.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def parse_as_of(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(date.fromisoformat(value), time(hour=12), tzinfo=UTC)


def main() -> int:
    args = parse_args()
    with SessionLocal() as session:
        summary = expire_raw(
            session,
            as_of=parse_as_of(args.date),
            dry_run=args.dry_run,
            force=args.force,
        )
        if not args.dry_run:
            session.commit()

    print(
        "expired raw rows: "
        f"candidates={summary.candidates} "
        f"deleted_unmatched={summary.deleted_unmatched} "
        f"deleted_matched={summary.deleted_matched} "
        f"skipped_unaggregated={summary.skipped_unaggregated} "
        f"dry_run={summary.dry_run}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
