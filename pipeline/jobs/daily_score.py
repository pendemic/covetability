from __future__ import annotations

import argparse
from datetime import date

from app.db import SessionLocal
from app.scoring.compute import run_daily_score


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute one day of shadow-mode Covetability scores.")
    parser.add_argument("--date", help="Observation date in YYYY-MM-DD format.")
    parser.add_argument(
        "--relist-precision",
        type=float,
        help="Measured relist-detection precision on the gold set (gates the turnover component).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    day = date.fromisoformat(args.date) if args.date else date.today()
    with SessionLocal() as session:
        summary = run_daily_score(session, day, relist_precision=args.relist_precision)
        session.commit()

    print(
        f"daily score date={day.isoformat()} scored={summary.bags_scored} "
        f"unscored={summary.bags_unscored} (published=false, shadow mode)"
    )
    print("bag,raw,smoothed,publication,classification,eligible,unscored_reason")
    for slug, stats in sorted(summary.bag_stats.items()):
        print(
            f"{slug},{stats['raw']},{stats['smoothed']},{stats['publication']},"
            f"{stats['classification']},{len(stats['eligible'])},{stats['unscored_reason'] or ''}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
