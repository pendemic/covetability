# Phase 3 - Condition normalization, relist detection, daily aggregates

## Context

Phases 0-2 are committed: schema (migrations 001-003), contract-as-code, 5-bag seed, fixture-first snapshot pipeline, matching engine with measured fixture precision, and the admin labeling/review surface. Phase 3 builds the durable asset (ADR-003): condition normalization (3.1), relist detection (3.2), the daily per-(bag x variant-nullable x band x day) aggregate table (3.3), backfill/recompute tooling for matcher re-baselines (3.4), and the aggregate-quality dashboard (3.5). Binding requirements: data-contract section 1.1 (winsorized 2/98, trailing 14-day window, at least 5 active matched listings per band else NULL price fields with counts still written), section 5 (row shape already field-for-field in `DailyAggregate`), section 1.3 (relist key seller + normalized title + image pHash, reappearance within 14 days becomes `possible_relist`), ADR-002 (condition accuracy at least 85%, adjacent-band confusions count as half errors), ADR-008 (exactly 6 bands), score-spec section 7 (>15% matched-set shift requires historical recompute). Everything runs on fixtures; live keys still pending.

## Decisions

- Separate-market variant listings feed only their variant aggregate row, never the model-level `variant_id NULL` row.
- Unbanded listings are excluded from banded rows and reported as a quality metric.
- "Active" means active at any point in the trailing 14-day window; day-D count is stored separately in `active_listing_count`.
- Aggregate writes are delete-then-insert per day and scope in one transaction.
- Relist detection runs as step 1 of the daily aggregate job; recompute never re-runs relist detection.
- pHash is source-polymorphic, computed only on insert or NULL backfill, and stored as a hash only.
- Accepted matched set is `ACCEPTED_STATUSES` from `app.matching.engine`.
- Price populations are USD-only.

## Design

Migration 004 adds `listings_raw.condition_normalizer_version`, indexes seller and listing-event date scans, and creates `aggregate_runs` as the append-only audit table for daily and recompute runs.

Condition normalization uses the six `ConditionBand` values as the scale order. Structured marketplace condition is primary evidence. Damage terms cap a structured band downward, positive title terms fill gaps only when structured condition is absent, and bare "Pre-owned" remains indeterminate unless the title carries usable evidence. Condition evaluation re-runs the current normalizer against gold labels and scores adjacent-band mistakes as half errors.

Relist detection keys on seller, effective bag, normalized title, and pHash. It writes `possible_relist` on the new or reappeared listing, keeps the prior `ended` event, and is idempotent by listing/event date. Live image fetch failures degrade to title-only matching; fixture sources can supply `fixturePhash`.

Daily aggregates route listings into either a model row or a separate-market variant row. Non-separate size/color variants remain in the model row. Price fields are written only when the group has at least `MIN_LISTINGS_PER_BAND`; thin rows keep counts and NULL prices. Recompute delete-inserts historical rows and refuses dates outside the raw-retention horizon.

The admin quality dashboard reports band coverage, active count trend, match-confidence trend, unbanded share, variant attribution share, separate-market rows, and alarms for zero candidates, missing aggregate days, and expired raw rows still present.

## Build Order

1. Schema + stats foundation: contract constants, migration 004, `AggregateRun`, Decimal stats.
2. Conditions: normalizer, snapshot wiring, re-normalization job, evaluator, fixture gold condition labels.
3. Relists + pHash: image hash helpers, ingestion plumbing, relist detection tests.
4. Aggregates + recompute: daily aggregate job, recompute job, verify job, workflow chain.
5. Quality dashboard + docs: admin quality API, web page, dev plan checkboxes.

## Verification

- Decimal winsorization and percentile unit tests.
- Condition evaluation against fixture gold labels passes the 0.85 target with coverage reported.
- Fixture relist scenarios emit one idempotent `possible_relist` event.
- Daily aggregates write thin rows with NULL price fields, priced rows with ordered p25/median/p75, and append `aggregate_runs`.
- Recompute delete-inserts stale rows and refuses dates beyond raw retention without force.
- Admin quality endpoint and page show band coverage, unbanded share, confidence trends, and alarms.
- CI runs migrate, seed, pytest, snapshot, verify, match, load gold, evaluate matcher, evaluate conditions, aggregate, verify aggregates, retention dry-run, and web lint/type/build.

## Key Files

New: `pipeline/alembic/versions/004_aggregates.py`, `pipeline/app/aggregates/{stats,relists,compute}.py`, `pipeline/app/conditions/{keywords,normalize,evaluate}.py`, `pipeline/app/ingestion/phash.py`, `pipeline/app/api/admin/aggregates.py`, `pipeline/jobs/{normalize_conditions,evaluate_conditions,daily_aggregates,recompute_aggregates,verify_aggregates}.py`, `pipeline/tests/test_{aggregate_stats,conditions,phash,relists,daily_aggregates}.py`, `web/app/admin/(app)/quality/page.tsx`.

Changed: contract constants, market models, ingestion models/source/snapshot, fixture gold labels, fixture workflows, Makefile, admin API/client/vocabulary/layout/CSS, and the Phase 3 development-plan checkboxes.

## Accepted Risks

- Mid-window-ended listings contribute their last price for up to 14 days.
- Relist prior and replacement can both be in the price window; the possible-relist count keeps that visible.
- Recompute reconstructs price from repriced events, but shipping and condition history are not evented.
- Saddle model-level rows can be thin by design because era variants are separate-market.
- Non-USD rows are excluded from price populations.
