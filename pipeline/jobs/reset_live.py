"""Clear synthetic seed data so real ingestion builds clean history.

The demo runs on synthetic market data (``jobs.seed_history``): daily aggregates,
weekly search signal, and published scores. Before switching to live sources you
want those gone so real snapshots/aggregates/scores accumulate from scratch. The
catalog (brands, bags, variants, aliases, exclusions, editorial) is preserved.

    uv run python -m jobs.reset_live                 # dry run: show what would be deleted
    uv run python -m jobs.reset_live --yes           # clear synthetic market data
    uv run python -m jobs.reset_live --yes --listings # also drop ingested listings/snapshots

Run this AFTER live credentials are configured and a first live pull is ready —
until then the public site will show no market data.
"""

from __future__ import annotations

import argparse

from sqlalchemy import delete, func, select, update

from app.db import get_session
from app.models import (
    BagModel,
    DailyAggregate,
    ListingEvent,
    ListingRaw,
    MatchRun,
    ScoreDaily,
    SearchSignalWeekly,
    SnapshotRun,
    TrendPull,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="Actually delete (otherwise dry run).")
    parser.add_argument("--listings", action="store_true", help="Also clear ingested listings/snapshots.")
    args = parser.parse_args()

    # (label, model) always cleared: synthetic market + score + search data.
    targets = [
        ("daily_aggregates", DailyAggregate),
        ("score_daily", ScoreDaily),
        ("search_signal_weekly", SearchSignalWeekly),
        ("trend_pulls", TrendPull),
    ]
    if args.listings:
        targets += [
            ("listing_events", ListingEvent),
            ("listings_raw", ListingRaw),
            ("match_runs", MatchRun),
            ("snapshot_runs", SnapshotRun),
        ]

    with next(get_session()) as session:
        print("Rows that will be cleared:" if args.yes else "Dry run — rows that WOULD be cleared:")
        for label, model in targets:
            count = session.scalar(select(func.count()).select_from(model))
            print(f"  {label}: {count}")

        if not args.yes:
            print("\nRe-run with --yes to apply (and --listings to also drop ingested listings).")
            return 0

        for _label, model in targets:
            session.execute(delete(model))
        # Un-publish every bag so scores return to shadow mode until real data re-earns publication.
        session.execute(update(BagModel).values(score_published=False, score_published_at=None))
        session.commit()
        print("\nDone. Catalog preserved; market/score/search data cleared. Bags returned to shadow mode.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
