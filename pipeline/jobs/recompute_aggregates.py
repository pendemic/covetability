from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.aggregates.compute import recompute_aggregates
from app.contract import RAW_RETENTION_DAYS
from app.db import SessionLocal
from app.models import BagModel


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recompute historical aggregate rows.")
    parser.add_argument("--since", required=True, help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--until", help="End date in YYYY-MM-DD format; defaults to today.")
    parser.add_argument("--bag", help="Limit to one bag slug.")
    parser.add_argument("--note", help="Free-text trigger note.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    since = date.fromisoformat(args.since)
    until = date.fromisoformat(args.until) if args.until else date.today()
    horizon = datetime.now(UTC).date() - timedelta(days=RAW_RETENTION_DAYS)
    if since < horizon:
        print(f"refusing recompute before raw retention horizon: {horizon.isoformat()}")
        return 2

    with SessionLocal() as session:
        bag_ids: set[int] | None = None
        if args.bag:
            bag_id = session.scalar(select(BagModel.id).where(BagModel.slug == args.bag))
            if bag_id is None:
                raise SystemExit(f"Unknown bag slug: {args.bag}")
            bag_ids = {bag_id}
        summary = recompute_aggregates(
            session,
            since,
            until,
            bag_ids=bag_ids,
            triggered_by=args.note,
        )
        session.commit()

    print(
        f"recomputed aggregates since={since.isoformat()} until={until.isoformat()} "
        f"rows={summary.rows_written}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
