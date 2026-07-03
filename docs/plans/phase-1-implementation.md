# Phase 1 — Ingestion (fixture-first, eBay-ready)

## Context

Phase 0 (foundations) is committed: schema migration 001, contract-as-code (`pipeline/app/contract.py`), 5-bag seed, CI. Phase 1 (dev plan `docs/development-plan.md:89-100`) builds the daily snapshot pipeline so it runs end-to-end **against fixtures today** and flips to live eBay with a config change the day keys arrive (access still pending per `docs/decisions/ebay-access.md`). Deliverables: eBay Browse client (1.1), fixture-replay source + ~30-listing-per-bag trap corpus (1.2), daily snapshot job (1.3), retention job (1.4), dormant scheduler workflow (1.5), and a written runbook for the 1.6 live smoke wait-gate.

**User decision:** fixture titles are synthetic-realistic, authored now (all trap cases from `docs/data/canonical-catalog.md` planted); real-researched titles can replace them later without code changes. The fixtures README records this provenance honestly.

## Existing code to build on

- `ListingRaw`/`ListingEvent`/`DailyAggregate` in `pipeline/app/models/market.py` — upsert key `uq_listings_raw_source_item (source, marketplace_item_id)`; `expires_at` NOT NULL (ADR-003 90-day window)
- `bag_models.initial_queries` JSONB (3 queries/bag) + slugs seeded by `pipeline/seeds/catalog.py`
- Constants/enums in `pipeline/app/contract.py` (`RAW_RETENTION_DAYS=90`, `SourceType.api`, `PriceType.asking`, `ListingEventType`)
- `pipeline/app/settings.py` (pydantic-settings), `pipeline/app/db.py` (`SessionLocal`), `pipeline/tests/conftest.py` (real-Postgres engine fixture), `Makefile`, `.github/workflows/ci.yml`
- No `snapshot_runs` table and no uniqueness on `listing_events` → migration 002

## Design

### Source abstraction (1.1 + 1.2 share one parsing path)

New modules in `pipeline/app/ingestion/`:

- `models.py` — pydantic models of eBay Browse shapes (`ItemSummary`, `SearchResponse`, `Money`, `ShippingOption`, `Item`; `extra="allow"` so `raw_payload` keeps the verbatim dict) + normalized `ListingCandidate` + `to_candidate(summary)`. Both sources emit `ItemSummary`, so fixture replay exercises exactly the live parsing path.
- `source.py` — `ListingSource` protocol (`source_name`, `mode`, `search_active_listings(query) -> Iterator[ItemSummary]`, `get_item(id)`), shared `slugify()`, and `get_listing_source(settings)` factory keyed on new `EBAY_SOURCE` setting (`fixtures` default | `live`; live without keys → clear RuntimeError).
- `fixtures.py` — `FixtureSource(fixtures_dir)`: reads `search/{slugify(query)}.json`, validates via `SearchResponse`; missing file → warn + empty (0-candidate bags surface in run counts). Dir is a constructor arg so tests copy the tree to tmp_path and simulate day N+1.
- `ebay.py` — `EbayBrowseClient` (sync **httpx** — new dep): OAuth client-credentials at `{base}/identity/v1/oauth2/token` (Basic app_id:cert_id, scope `https://api.ebay.com/oauth/api_scope`), token cached with expiry + one re-auth retry on 401; base URL from `EBAY_ENVIRONMENT` (production/sandbox); `GET /buy/browse/v1/item_summary/search` with `q`, `category_ids` (setting, default `169291`, verified at 1.6), `filter=buyingOptions:{FIXED_PRICE|BEST_OFFER}` (auction bids aren't asking prices), `X-EBAY-C-MARKETPLACE-ID` (default `EBAY_US`), limit=200/offset pagination capped at 1000/query, 429 → Retry-After/backoff then `EbayApiError`; injectable `httpx.BaseTransport` for MockTransport tests; optional `record_dir` writes every page verbatim in fixture-compatible format (the 1.6 bridge from live data to fixtures — satisfies "every request/response serializable to disk").

Settings additions (+ `.env.example`): `EBAY_SOURCE=fixtures`, `EBAY_MARKETPLACE_ID=EBAY_US`, `EBAY_CATEGORY_IDS=169291`, `EBAY_FIXTURES_DIR=fixtures/ebay` (resolved relative to package root), `EBAY_RECORD_DIR` (optional).

### Fixture corpus (1.2)

`pipeline/fixtures/ebay/search/{slugify(query)}.json` — 15 files (5 bags × 3 seeded queries), each shaped exactly like a Browse search response. Per bag: ~30 unique listings spread over its 3 files, 2–4 deliberate cross-query duplicates (same itemId — exercises dedup/upsert forever), itemIds namespaced `v1|fx…|0` (`fx` = test-cleanup handle; IDs stable forever — Phase 2 gold labels will reference them). Mixed conditions/shipping/missing-field variance. Planted traps per catalog doc, ≥1 replica/"inspired" and ≥1 accessory trap per bag:

- Paddington: Paddington Bear plush/DVD/marmalade merch, Chloé Edith/Silverado mislabels
- City: Balenciaga **First** mislabeled City, **Le City** 2024 reissue, Town/Work/Part-Time, "moto style dupe"
- Baguette: Mama/Mamma Forever, croissant, baguette **charm**, Peekaboo mislabel
- Saddle: equestrian horse saddle/saddle pad/western tack, Gucci saddle, "saddle style"
- Pochette: chain strap only, insert/organizer, Mini Pochette, Métis/Félicie, "LV inspired"

`pipeline/fixtures/ebay/README.md`: synthetic-title provenance note, trap inventory table (file, itemId, trap, expected rejection reason), itemId-stability rule. **These fixtures are the Phase 2 matcher's first test corpus.**

### Migration 002 (`pipeline/alembic/versions/002_snapshot_runs.py`)

- New contract enums `IngestionMode(fixtures|live)`, `SnapshotRunStatus(succeeded|partial|failed)`; new constant `ENDED_AFTER_MISSED_DAYS = 2`.
- `snapshot_runs` table (append-only audit log; a same-day re-run adds a row — the *data* is what's idempotent): id, run_date (indexed), source, mode, status, started_at/finished_at, `bag_counts` JSONB (`{slug: {fetched, unique, inserted, updated, repriced, query_errors[]}}`), ended_event_count, error, created_at. New `SnapshotRun` model in `models/market.py`, exported.
- Unique constraint `listing_events (listing_id, type, event_date)` — idempotency backstop; all event writes use `INSERT … ON CONFLICT DO NOTHING`.

### Snapshot job (1.3)

Core `run_snapshot(session, source, *, as_of=None)` in `app/ingestion/snapshot.py` (`as_of` defaults now-UTC; tests inject it to simulate multi-day sequences). Per bag (ordered by slug) → per `initial_queries` → fetch → `to_candidate` → ORM select-then-write upsert loop on `(source='ebay', marketplace_item_id)` (~150 rows/day; boring beats bulk):

- Insert: constants `source_type=api`, `price_type=asking`, `match_confidence=NULL` (matching is Phase 2), `first_observed=observed_at=last_observed=as_of`, `expires_at=as_of+90d`; emit `new` event.
- Update: refresh title/price/shipping/seller/url/condition_raw/raw_payload, `last_observed=as_of`, **`expires_at=as_of+90d` (rolling window — expires 90d after last seen)**; on price change also emit `repriced` with `{old_price, new_price, currency}` (cheap now; Phase 5's repricing guard wants this history).
- **Ended detection** (after all 15 queries; global, not per-bag — Phase 1 rows are unmatched): listing not in the run's union seen-set AND `run_date − last_observed ≥ ENDED_AFTER_MISSED_DAYS` (N=2: one missed day may be a query hiccup) AND no `ended` event since `last_observed` → `ended` event (`event_date=run_date`, payload `{last_observed, days_absent}`). Reappearance after `ended` just rolls `last_observed` forward (relist interpretation is Phase 3.2).
- **Partial-run guard:** any query exception → caught, recorded in `bag_counts[slug].query_errors`, run `status=partial`, **ended detection skipped entirely** (a broken query must never read as a wave of endings).
- Writes the `snapshot_runs` row; returns a `SnapshotSummary` dataclass. Caller commits.

CLI wrapper `pipeline/jobs/daily_snapshot.py` (pattern of `python -m seeds.catalog`): argparse `--date` (as_of override), `--record`; prints per-bag table; exit 1 only on `status=failed`.

### Retention job (1.4)

`expire_raw(session, *, as_of=None, dry_run=False, force=False)` in `app/ingestion/retention.py`; wrapper `jobs/expire_raw.py` with `--dry-run`/`--force`. Candidates: `expires_at < as_of`.

- Unmatched rows (`matched_bag_model_id IS NULL` — all of Phase 1): delete unconditionally (never fed aggregates).
- Matched rows: delete only if a `daily_aggregates` row exists for that bag with `observation_date >= last_observed::date`; else skip + count (`skipped_unaggregated`) + warn, **exit 0** (safe state until Phase 3 ships; persistent skips become a Phase 3.5 alarm). `--force` bypasses.
- Event cascade-on-delete is intended ADR-003 behavior (lifecycle *counts* persist in aggregates); documented in module docstring + proven by test.

### Scheduler (1.5) + Make/CI

- `.github/workflows/snapshot.yml`: cron `17 6 * * *` + `workflow_dispatch`; job-level `if: vars.EBAY_LIVE_ENABLED == 'true'` → exists but skips until the variable is set at 1.6 (secrets `SNAPSHOT_DATABASE_URL`, `EBAY_APP_ID`, `EBAY_CERT_ID` also created then). Steps: uv sync → `python -m jobs.daily_snapshot` → `python -m jobs.expire_raw`.
- `Makefile`: `EBAY_SOURCE ?= fixtures`; targets `snapshot` (`cd pipeline && EBAY_SOURCE=$(EBAY_SOURCE) uv run python -m jobs.daily_snapshot`), `expire`, `expire-dry` (+.PHONY). `make snapshot EBAY_SOURCE=fixtures` is literally the verification command.
- `.github/workflows/ci.yml` pipeline job, after pytest: run fixture snapshot → assert counts (≥120 raw rows, events == rows, run row exists; small `jobs/verify_snapshot.py` helper) → re-run → assert unchanged → `expire_raw --dry-run`. This is the standing "one simulated day on fixtures completes in CI" e2e.

### 1.6 wait-gate (runbook only — no execution this phase)

Extend `docs/decisions/ebay-access.md` with a "Live smoke runbook": enter keys → `EBAY_SOURCE=live EBAY_RECORD_DIR=… make snapshot` → verify Paddington volume 200–600 + category 169291 + rate-limit headroom → provision hosted Postgres, migrate+seed, set secrets → flip `EBAY_LIVE_ENABLED=true` → watch first scheduled run → mint real fixtures from recordings.

## Build order (~4 sessions)

1. **Plumbing:** httpx dep; contract additions; settings; migration 002 + `SnapshotRun` model (verify downgrade/upgrade round-trip); `ingestion/models.py`, `source.py`, `fixtures.py`; one starter fixture file; unit tests green.
2. **Fixture corpus:** all 15 files + README trap table; `test_fixture_source.py` incl. per-bag count (≥25) and trap-presence regressions keyed off `seeds.catalog.CATALOG` so corpus and seed can't drift.
3. **Jobs:** `snapshot.py`, `retention.py`, `jobs/` wrappers, Makefile targets; integration tests; manual `make snapshot EBAY_SOURCE=fixtures` twice + `make expire-dry`.
4. **Live client + ops:** `ebay.py` + MockTransport tests (token cache/refresh/401, pagination, 429, sandbox vs prod URLs, recorder↔FixtureSource compatibility); `snapshot.yml`; CI e2e steps; 1.6 runbook; tick dev-plan checkboxes 1.1–1.5; full `make lint test` + CI green.

## Key files

New: `pipeline/app/ingestion/{models,source,fixtures,ebay,snapshot,retention}.py` · `pipeline/jobs/{__init__,daily_snapshot,expire_raw}.py` · `pipeline/alembic/versions/002_snapshot_runs.py` · `pipeline/fixtures/ebay/README.md` + `search/*.json` (15) · `pipeline/tests/test_{ingestion_models,fixture_source,ebay_client,daily_snapshot,expire_raw}.py` · `.github/workflows/snapshot.yml`

Changed: `pipeline/app/contract.py` · `pipeline/app/settings.py` + `.env.example` · `pipeline/app/models/market.py` + `models/__init__.py` · `pipeline/pyproject.toml` · `Makefile` · `.github/workflows/ci.yml` · `docs/decisions/ebay-access.md` · `docs/development-plan.md` (checkboxes)

## Verification (maps to the dev plan's Phase 1 exit criteria)

1. `make db-up migrate seed && make snapshot EBAY_SOURCE=fixtures` populates `listings_raw` + `new` events for **all 5 bags**; `snapshot_runs` row has all 5 slugs with counts.
2. Re-run same day → row/event counts unchanged (idempotent); second run-log row recorded.
3. Integration test: fixture tree copied, one listing removed → day D+1 no `ended` (N=2), day D+2 exactly one `ended`; re-run still one. Price change → one `repriced` with old/new payload.
4. Retention test: expired unmatched row deleted; expired **matched** row deleted only when its bag has covering `daily_aggregates` — and the aggregate row provably survives; no-aggregates case skipped unless `--force`; `--dry-run` deletes nothing.
5. Live client tests pass with zero network (MockTransport); recorded pages load through `FixtureSource`.
6. CI green including the new fixture-snapshot e2e + idempotency check.

## Defaults chosen (revisit at 1.6, none block)

Auction listings excluded via buyingOptions filter (asking-price product) · category 169291 unverifiable until live · hosted Postgres provisioning deferred to 1.6 runbook · `ENDED_AFTER_MISSED_DAYS=2` tunable against live query stability.
