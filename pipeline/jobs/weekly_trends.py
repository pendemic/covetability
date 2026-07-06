from __future__ import annotations

import argparse

from app.db import SessionLocal
from app.settings import get_settings
from app.trends.ingest import run_weekly_trends
from app.trends.source import get_trend_source


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pull/import trends and stitch weekly search signal.")
    parser.add_argument("--anchor", help="Anchor term override.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    anchor = args.anchor or settings.trends_anchor_term
    source = get_trend_source(settings)

    with SessionLocal() as session:
        summary = run_weekly_trends(session, source, anchor_term=anchor)
        session.commit()

    print(f"weekly trends source={source.source_name} anchor={anchor}")
    print("bag,pulls,weeks,latest_bucket,alias_agrees,low_volume")
    for slug, stats in sorted(summary.bag_stats.items()):
        print(
            f"{slug},{stats['pulls_written']},{stats['weeks']},"
            f"{stats['latest_bucket']},{stats['latest_alias_agrees']},{stats['latest_low_volume']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
