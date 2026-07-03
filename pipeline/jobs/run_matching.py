from __future__ import annotations

import argparse

from app.db import SessionLocal
from app.matching.engine import apply_matching
from app.matching.matcher import CatalogIndex


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply listing matching rules.")
    parser.add_argument("--all", action="store_true", help="Re-match all non-human-decided listings.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with SessionLocal() as session:
        summary = apply_matching(
            session,
            CatalogIndex.from_session(session),
            only_pending=not args.all,
        )
        session.commit()

    print(
        f"match run mode={summary.mode} considered={summary.listings_considered} "
        f"pinned={summary.pinned_count}"
    )
    print("status,count")
    for status, count in sorted(summary.status_counts.items()):
        print(f"{status},{count}")
    if summary.bag_deltas:
        print("bag,before,after,added,removed,delta_pct")
        for slug, delta in summary.bag_deltas.items():
            print(
                f"{slug},{delta['before']},{delta['after']},"
                f"{len(delta['added'])},{len(delta['removed'])},{delta['delta_pct']}"
            )
        if summary.threshold_exceeded:
            print("rematch delta threshold exceeded; aggregate recompute required in Phase 3.4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
