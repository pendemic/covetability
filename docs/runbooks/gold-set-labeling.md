# Gold-Set Labeling Runbook

Phase 2.6 starts only after Phase 1.6 live eBay smoke testing is complete and live snapshots are running.

## Preconditions

- Production Browse API credentials are active.
- A live snapshot has populated candidates for all five pilot bags.
- `make match` has run after the snapshot.
- The admin web app has `PIPELINE_API_URL` and `ADMIN_SECRET` set server-side.

## Sampling Plan

Label candidates from `/admin/labeling` in queue order by candidate bag. Target 150-200 labels per bag. Do not skip query-noise rows; those rejects define the recall denominator and expose leaking exclusions.

## Tuning Loop

1. Label about 50 candidates per bag.
2. Run `make evaluate GOLD=human`.
3. Read the false-positive reason table and confusion export.
4. Tune aliases and exclusions in `pipeline/seeds/catalog.py`.
5. Run `make seed`, bump `MATCHER_VERSION` for rule changes, then run `make rematch`.
6. If any rematch delta exceeds 15%, keep the `match_runs` row and run `make recompute SINCE=<first-affected-date> NOTE="match_run=<id>"` before treating downstream movement as real.
7. Repeat until precision is at least 95%, recall is at least 70%, and variant attribution is at least 85%.

## Exit

Paste the final evaluation report into the Phase 2 notes, then mark 2.6 complete. Fixture labels do not satisfy the real-data launch gate; they are CI regressions only.
