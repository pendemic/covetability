# Phase 2 — Matching engine + gold-set tooling

## Context

Phases 0–1 are committed: schema (migrations 001–002), contract-as-code, 5-bag seed, and the fixture-first snapshot pipeline running end-to-end in CI. Phase 2 (dev plan `docs/development-plan.md:104-116`) is the actual pilot experiment (ADR-002): match listings to canonical bags at **measured** precision, and build the human labeling workflow that proves it. Deliverables: title normalizer (2.1), rule-based matcher v1 with stored rule traces (2.2), admin shell + shared-secret auth + ingestion dashboard (2.3), keyboard-driven gold-set labeling UI (2.4), precision harness (2.5), match review queue (2.7), and a runbook for the 2.6 wait-gate (labeling real data waits on eBay keys / task 1.6). Everything runs fixture-only; the 25 planted traps in `pipeline/fixtures/ebay/` become permanent CI regressions. Targets: precision ≥95% model-level, recall ≥70%, variant attribution ≥85%.

**Decisions this plan settles:** match state lives as columns on `listings_raw` (traces are deterministic and regenerable — no history table); candidate-bag provenance is recorded at snapshot time; extractor keyword tables are code constants while aliases/exclusions stay in the DB (operator-tuned during 2.6); admin traffic flows browser → Next route-handler proxy → FastAPI so `ADMIN_SECRET` never reaches the client; fixture expected-labels are a structured JSON artifact loaded into `gold_labels` so evaluation has one code path for fixture and human labels.

## Existing code to build on

- `ListingRaw` (`pipeline/app/models/market.py:40`) already has `matched_bag_model_id` / `matched_variant_id` / `match_confidence` (0–1 check) — but no status/trace/version columns and no index on `matched_bag_model_id`. `GoldLabel` (`market.py:222`) exists but has **no bag-context column, no unique key, no reject⇒reason constraint** — and is empty everywhere, so migration 003 can tighten it freely.
- `run_snapshot()` / `upsert_listing(session, source_name, candidate, observed_at)` (`pipeline/app/ingestion/snapshot.py:35,114`) does not record which bag's query fetched a listing; `bag` is in scope at the call site (`snapshot.py:80`) — cheap to change now.
- Thresholds `MATCH_AUTO_ACCEPT = 0.90`, `MATCH_REVIEW_FLOOR = 0.60` (`pipeline/app/contract.py:104-105`), `RejectionReason` (10 values), `GoldLabelVerdict`, `ConditionBand`, `VariantKind` all exist; `tests/test_contract.py` asserts constants verbatim — new constants get asserted there too.
- Catalog seeded by `pipeline/seeds/catalog.py`: ~40 aliases, ~32 global + per-bag exclusions as `(term, RejectionReason)` tuples, `BagVariant.is_separate_market` (Le City reissue, Dior vintage/modern, Baguette re-edition, Pochette NM). `CATALOG` / `GLOBAL_EXCLUSIONS` are importable → matcher unit tests can build an index without Postgres.
- Fixture corpus: 15 files, ~150 listings, stable ids `v1|fx-…|0`; README trap table (25 traps + the Le City separate-market accept `v1|fx-balenciaga-city-007|0`). `raw_payload` keeps `image.imageUrl` (fake URLs — UI must survive broken images).
- FastAPI is bare `/health` (`app/main.py`); `app/api/` and `app/matching/` are empty stubs; `settings.admin_secret` (`ADMIN_SECRET`) exists unused.
- Migration house style (see `002_snapshot_runs.py`): revision id == filename stem, local `create_pg_enum`/`pg_enum(create_type=False)` helpers, named constraints; existing PG enums referenced with `create_type=False`; `down_revision = "002_snapshot_runs"`.
- Tests: real-Postgres `db_engine` fixture, cleanup-helper isolation (`'v1|fx%'`, `'test-bag-%'`), `create_test_bag()`.
- Web: plain global-CSS tokens, strict TS, `@/*` alias, no fetch/env/middleware anywhere. `web/scripts/vocab-lint.mjs` scans **all** of `app/` + `lib/` (admin included) — the 14 banned patterns verified; proposed admin display strings all pass.

## Design

### Contract + migration 003 (`pipeline/alembic/versions/003_matching.py`)

New in `contract.py` (+ asserts in `test_contract.py`):
- `MatchStatus(StrEnum)`: `pending | auto_accepted | needs_review | auto_rejected | human_accepted | human_rejected` (`pending` = server default; `human_*` set only by review decisions and never overwritten by re-matching).
- `GoldLabelOrigin(StrEnum)`: `labeling_ui | review_queue | fixture_seed`.
- Constants: `REMATCH_DELTA_THRESHOLD = 0.15` (score-spec §7), `MATCH_PRECISION_TARGET = 0.95`, `MATCH_RECALL_TARGET = 0.70`, `VARIANT_ATTRIBUTION_TARGET = 0.85`.

Migration 003:
- `listings_raw` += `match_status` (NOT NULL, default `'pending'`), `rule_trace` JSONB, `matcher_version` String(40), `matched_at` timestamptz, `candidate_bag_model_id` FK SET NULL, `candidate_query` String(240). Indexes: `matched_bag_model_id` (overdue; Phase 3 wants it), `match_status`, `candidate_bag_model_id`.
- `gold_labels` hardening: add `bag_model_id` FK CASCADE **NOT NULL** (a verdict is always relative to a candidate bag — reject labels are unevaluable without it); `origin` enum NOT NULL default `labeling_ui`; `marketplace_item_id` → NOT NULL (the durable key; `listing_id` goes NULL on raw expiry); `uq_gold_labels_item_bag (marketplace_item_id, bag_model_id)` (relabeling upserts); `ck_gold_labels_verdict_reason` (`reject` ⇔ reason present, `accept` ⇔ reason NULL); index on `bag_model_id`.
- New table `match_runs` (append-only, `snapshot_runs` precedent): `run_at`, `mode` (`incremental|full`, plain String), `matcher_version`, `listings_considered`, `status_counts` JSONB, `bag_deltas` JSONB (`{slug: {before, after, added, removed, delta_pct}}`, full mode), `threshold_exceeded` bool, `notes` — the durable matched-set-delta log required by 2.6.

### Candidate-bag provenance (snapshot change)

`upsert_listing()` gains `bag_id` / `query` args: set both on insert; on update fill **only if NULL** (first-fetch provenance sticks; also backfills pre-003 dev rows on the next snapshot for free). Rationale: a query-hits join table is over-general for 5 brand-disjoint bags, and matcher-derived attribution fails exactly where it matters — "horse saddle western tack" has no Dior signal but must queue as a `dior-saddle` candidate because the Dior query fetched it. The labeling queue and the recall denominator are defined by this column.

### Normalizer (2.1) — `pipeline/app/matching/normalize.py` + `keywords.py`

- `normalize_title(raw) -> NormalizedTitle` (`raw`, `text`, `tokens`): lowercase → NFKD de-accent (same technique as `source.slugify`) → punctuation→spaces → collapse. `contains_term()` matches on word boundaries after normalizing the term the same way (`Part-Time` ⇒ `part time` matches).
- Extractors (pure functions): `extract_measurements` (regex for `NN cm`, `NN"`, `NN x NN` — runs before punctuation strip so `9"` survives), `extract_size(bag_slug, …)`, `extract_color_family(bag_slug, …)`, `extract_edition(bag_slug, …)`.
- `keywords.py`: per-bag tables hand-transcribed from `docs/data/canonical-catalog.md` — `CONFIRMING_SIGNALS` (padlock/clochette; moto/tassels/agneau/chèvre/G12/G21; zucca/FF clasp; oblique/stirrup/trotter/galliano; monogram/damier/azur/multicolore/vernis/vachetta), `SIZE_TERMS`, `COLOR_FAMILIES`, `EDITION_RULES` (`le city|2024 reissue → "Le City reissue"`, NM/re-edition per bag), measurement→size bands where the catalog says measurements beat titles (City, Pochette). **Code, not DB**: extractor tables change only with matcher code and are covered by `MATCHER_VERSION`; aliases/exclusions remain the DB-seeded, operator-tuned catalog.

### Matcher v1 (2.2) — `pipeline/app/matching/matcher.py`

- `CatalogIndex` with `from_session(session)` and `from_seed()` (unit tests, no PG); a PG test asserts both constructors produce identical indexes so they can't drift.
- `match_listing(title, index, candidate_bag_slug=None) -> MatchResult(bag_slug|None, variant_name|None, confidence, status, trace)`. Per candidate bag (brand token or alias present): brand detect → alias/model match → exclusion scan (every hit recorded with reason) → size/color/edition extraction → additive score clamped [0,1]; best bag wins, provenance bag breaks ties. No alias hit anywhere → confidence 0.0 `auto_rejected`, but the exclusion scan still runs against the provenance bag so the trace carries `suggested_rejection_reason` for the labeling UI.
- **Weights** (constants; tuned in session 5 until the fixture harness passes): brand token **+0.30** · alias/model-name **+0.45** · confirming signal **+0.10 each, cap +0.20** · variant extracted **+0.05** · exclusion **−0.60 per distinct term**. Anatomy vs thresholds: brand+alias = 0.75 → review (uncorroborated "Balenciaga City" deserves eyes); +1 signal +variant = 0.90 → auto-accept; alias without brand = 0.45–0.60 → reject/review floor; any exclusion drops a perfect 1.00 to ≤0.40 → auto-reject with the reason on record (a weight, not a special case — the trace stays one honest arithmetic).
- Status: `≥0.90 → auto_accepted`, `≥0.60 → needs_review` (matched fields set; consumers filter on status), else `auto_rejected` (matched fields NULL; context lives in provenance + trace). Separate-market variants are accepts attributed to that variant; splitting them out of aggregates is Phase 3's concern.
- `MATCHER_VERSION = "1.0"`; rule: bump on any weight/keyword/alias-handling change.
- `rule_trace` JSON shape (stored verbatim, rendered by both UIs): `{matcher_version, normalized_title, candidates: [{bag_slug, confidence, hits: [{rule, term, weight}], exclusions: [{term, scope, reason, weight}], variant}], selected, status, suggested_rejection_reason}`.

### Matching execution — `pipeline/app/matching/engine.py` + `jobs/run_matching.py`

- `apply_matching(session, index, *, only_pending=True)`: ORM loop (~150 rows/day; boring beats bulk) writing the six match columns. `human_*` rows are **pinned** — skipped and counted; operator decisions are ground truth (evaluation re-runs the matcher in memory anyway, so pinning hides nothing).
- Full mode (`--all`): per-bag before/after sets of `auto_accepted|human_accepted` listing ids; `delta_pct = (|added|+|removed|)/max(1,|before|)`; writes `match_runs` with `bag_deltas`, sets `threshold_exceeded` when any bag > 0.15, prints a per-bag delta table with a "recompute required — Phase 3.4" warning. Historical aggregate recompute itself is deferred to 3.4 (no aggregates exist yet); the 2.6 requirement satisfied now is the **logged delta**.
- CLI `jobs/run_matching.py` (house pattern): default incremental, `--all` full; every invocation writes a `match_runs` row. Chained after snapshot in `.github/workflows/snapshot.yml` (dormant) and the CI e2e. Makefile: `match`, `rematch`.

### Fixture gold set + evaluation harness (2.5)

- `pipeline/fixtures/ebay/expected_labels.json`: one entry per fixture listing (~150 — recall needs the accepts, not just the 25 traps): `{item_id, bag_slug, verdict, rejection_reason, variant, color_family, note}`. `v1|fx-balenciaga-city-007|0` = accept + variant "Le City reissue". A pytest cross-checks every README trap id appears with the same reason (the JSON is the single source of truth; README stays prose).
- `jobs/load_fixture_gold.py`: upserts the JSON into `gold_labels` (`origin=fixture_seed`, `labeled_by="fixture"`, variant names → `accepted_variant_id`). After this, one evaluation code path for fixture and human labels.
- `matching/evaluate.py`: per gold label, look up the listing by `(source, marketplace_item_id)` and run the matcher **fresh in memory** (measures current rules — the 2.6 tune→re-measure loop needs no rematch round-trip); expired raw rows counted `unevaluable`. Model-level definitions: **TP** = gold accept for bag b, matcher auto-accepts to b; **FP** = matcher auto-accepts to b but gold rejects for b (attributed to the gold reason → false-positive category table) or gold-accepts elsewhere; **FN** = gold accept not auto-accepted to b. Precision TP/(TP+FP); recall TP/(TP+FN); gold accepts landing in the review band reported as their own row (recoverable by human review). **Variant attribution**: among TPs with a gold variant, predicted == gold. Targets asserted against the contract constants.
- CLI `jobs/evaluate_matcher.py`: `--bag`, `--gold-origin fixture_seed|human|all`, `--export path.csv` (confusion listing: item, title, gold, predicted, confidence, top hits), `--enforce` (exit 1 below targets).
- **CI**: after the existing snapshot steps — `run_matching` → `load_fixture_gold` → `evaluate_matcher --gold-origin fixture_seed --enforce`; plus pytest trap regressions (no gold-reject ever auto-accepted; no gold-accept auto-rejected; Le City → separate-market variant).

### Admin API (2.3/2.4/2.7) — `pipeline/app/api/admin/`

`__init__.py` (router, prefix `/admin`), `deps.py`, `schemas.py`, `ingestion.py`, `labeling.py`, `review.py`; wired in `app/main.py` (`/health` stays open).

- **Auth**: `require_admin` dependency — `Authorization: Bearer <ADMIN_SECRET>` via `secrets.compare_digest`; 401 otherwise. No CORS (browser never calls FastAPI directly).
- Endpoints (list envelopes `{items, total, limit, offset}`; limit default 50, max 200):
  - `GET /admin/ingestion/summary` — recent `snapshot_runs` (per-bag counts, query_errors, error rate), last `match_runs` row, per-bag `match_status` distribution, gold-label progress.
  - `GET /admin/catalog/bags` — slugs/names/variants (kind, is_separate_market) + per-bag color families (from `keywords.py`) for the accept form.
  - `GET /admin/labeling/queue/next?bag=slug&after_id=` — next `listings_raw` where `candidate_bag_model_id=bag` and `(marketplace_item_id, bag)` ∉ `gold_labels`, ordered by id; **includes auto-rejects** (the queue is defined by provenance, not matcher verdict — else recall is unmeasurable). Payload: title, price/shipping, condition_raw, seller, candidate_query, `image_url` (extracted server-side from `raw_payload.image.imageUrl`), matcher guess + full `rule_trace`, remaining count.
  - `POST /admin/labels` — upsert on `(marketplace_item_id, bag_model_id)`: verdict, reason?, variant?, color_family?, condition_band?, five completeness bools, notes?, `origin=labeling_ui`. Labeling writes gold truth only — never match columns.
  - `GET /admin/review/queue?bag=&limit=&offset=` — `needs_review` rows with traces.
  - `POST /admin/review/{listing_id}/decision` — `{action: approve|reassign|reject, bag_model_id?, variant_id?, rejection_reason?}`: approve → `human_accepted`; reassign → `human_accepted` + new bag/variant; reject → `human_rejected` + matched fields NULL. Each decision **also upserts a gold label** (`origin=review_queue`) — review feeds the gold set by construction.

### Web admin (2.3/2.4/2.7) — `web/app/admin/`

- **Auth (cookie + proxy)**: `web/app/api/admin-session/route.ts` — POST `{secret}` vs `process.env.ADMIN_SECRET` via `crypto.timingSafeEqual`; sets httpOnly cookie `admin_session = HMAC_SHA256(ADMIN_SECRET, "covetability-admin-v1")` (SameSite=Lax, 30d; stateless, secret never client-side); DELETE clears. `web/app/api/admin/[...path]/route.ts` — verifies cookie, forwards to `${PIPELINE_API_URL}/admin/...` adding the bearer header. Helpers in `web/lib/adminAuth.ts` (node:crypto, server-only).
- Routes: `admin/login/page.tsx` + route group `admin/(app)/` — server-component `layout.tsx` (cookie check → `redirect("/admin/login")`; nav Dashboard · Labeling · Review · logout) wrapping `page.tsx` (dashboard), `labeling/page.tsx`, `review/page.tsx` (client components using `web/lib/adminApi.ts` — hand-written typed fetchers mirroring the pipeline schemas).
- **Dashboard**: snapshot-run table, per-bag match-status distribution, gold-label progress — one `getIngestionSummary()` call.
- **Labeling screen** (the 750–1000-label grind): one card — big title, price+shipping, condition_raw, seller, fetching query, image via plain `<img>` with `onError` → "no image" placeholder (fixtures always hit this; `eslint-disable` for `no-img-element`, honest until remotePatterns matter) — plus matcher panel: status chip, confidence, trace hits as weighted rows, exclusions in red with reason, `suggested_rejection_reason` pre-highlighted. **Keyboard map**: `a` accept · `r` reject · `n` skip · `u` previous · `?` help; reject strip `1–9,0` = the ten taxonomy reasons in contract order (reject = 2 keystrokes); accept wizard: variant `1–9`/`0` skip → color family → condition band `1–6`/`0` → completeness toggles `s/l/k/d/c` → `Enter` (≈5 keystrokes); `Backspace` back, `Esc` cancel; next candidate prefetched during entry.
- **Review screen**: queue table (title, price, guess, confidence, compact trace chips) with expandable trace+image panel; `j/k` navigate, `a` approve, `m` reassign → bag `1–5` → optional variant, `r` reject → reason keys.
- Styling: `web/app/admin/admin.css`, `.admin*`-prefixed classes reusing existing tokens — no framework. Display strings in `web/lib/adminVocabulary.ts`, deliberately **not** allowlisted in vocab-lint (keeps admin copy honest; all proposed strings pass).
- Env: new `web/.env.example` — `PIPELINE_API_URL=http://localhost:8000`, `ADMIN_SECRET=change-me` (server-side only, no `NEXT_PUBLIC_`).

### 2.6 wait-gate runbook (docs only)

New `docs/runbooks/gold-set-labeling.md` (ebay-access.md gains a pointer line): preconditions (1.6 done, live snapshots + `make match`); sampling plan (label per candidate bag in queue order to 150–200/bag; Pochette will be majority rejects — that's the stress test, label them anyway); cadence (~200 labels/hour ⇒ ~5 sessions); the tuning loop — label ~50/bag → `make evaluate GOLD=human` → read the FP-reason table → tune exclusions/aliases in `seeds/catalog.py` + `make seed` → bump `MATCHER_VERSION` → `make rematch` (>15% delta on any bag → `threshold_exceeded`, annotate; once 3.4 exists, run the historical recompute — score-spec §7: "a matcher change must never appear as a market event") → re-evaluate → repeat to ≥95/≥70/≥85, paste the final report, tick 2.6.

## Build order (~8 sessions, strictly ordered)

1. **Schema + provenance**: contract additions + `test_contract.py`; migration 003 (upgrade/downgrade round-trip); model updates (`ListingRaw` columns, `GoldLabel` hardening, `MatchRun`); snapshot provenance change + updated snapshot tests; gold-label constraint tests.
2. **Normalizer (2.1)**: `normalize.py`, `keywords.py`; unit tests from real fixture titles (accents, hyphens, measurements, per-bag extractors).
3. **Matcher (2.2)**: `CatalogIndex` (from_seed/from_session parity test), scoring, trace; tests: one clean accept per bag, every trap category, Le City, alias-without-brand → review, exclusion arithmetic.
4. **Engine + jobs + gold artifact**: `engine.py`, `jobs/run_matching.py`, author `expected_labels.json` (~150 rows), `jobs/load_fixture_gold.py`, README↔JSON cross-check test; Makefile `match`/`rematch`; PG integration tests (snapshot → match → statuses, idempotent re-run, injected delta >15% flagged, human rows pinned).
5. **Evaluate (2.5) + CI**: `evaluate.py` + `jobs/evaluate_matcher.py`; tune weights/keywords until the fixture corpus passes `--enforce`; trap-regression pytest; CI steps (match → load gold → enforce) + snapshot.yml match step; Makefile `evaluate`/`evaluate-fixtures`.
6. **Admin API**: `app/api/admin/`, `main.py` wiring; TestClient tests (401s, summary shape, queue next/submit/upsert/advance, review decision writes gold label + flips status, pagination).
7. **Web shell + auth + dashboard (2.3)**: `adminAuth.ts`, session + proxy routes, login, `(app)` layout/nav/`admin.css`, dashboard, `adminApi.ts`, `web/.env.example`; add `npm run build` to the CI web job.
8. **Labeling + review UIs + docs (2.4/2.7/2.6-prep)**: labeling wizard with full keyboard map, review queue, `adminVocabulary.ts`; manual round-trip (label 20 via UI → `make evaluate` reflects them); `docs/runbooks/gold-set-labeling.md`; tick dev-plan boxes 2.1–2.5, 2.7; commit this plan as `docs/plans/phase-2-implementation.md`.

## Key files

New: `pipeline/app/matching/{normalize,keywords,matcher,engine,evaluate}.py` · `pipeline/app/api/admin/{__init__,deps,schemas,ingestion,labeling,review}.py` · `pipeline/jobs/{run_matching,load_fixture_gold,evaluate_matcher}.py` · `pipeline/alembic/versions/003_matching.py` · `pipeline/fixtures/ebay/expected_labels.json` · `pipeline/tests/test_{normalize,matcher,matching_engine,evaluate,admin_api}.py` · `web/app/admin/login/page.tsx` · `web/app/admin/(app)/{layout,page,labeling/page,review/page}.tsx` · `web/app/admin/admin.css` · `web/app/api/admin-session/route.ts` · `web/app/api/admin/[...path]/route.ts` · `web/lib/{adminAuth,adminApi,adminVocabulary}.ts` · `web/.env.example` · `docs/runbooks/gold-set-labeling.md` · `docs/plans/phase-2-implementation.md`

Changed: `pipeline/app/contract.py` · `pipeline/app/models/market.py` + `models/__init__.py` · `pipeline/app/ingestion/snapshot.py` · `pipeline/app/main.py` · `pipeline/tests/{test_contract,test_daily_snapshot,test_schema_constraints}.py` · `Makefile` · `.github/workflows/{ci,snapshot}.yml` · `docs/decisions/ebay-access.md` · `docs/development-plan.md`

## Verification (maps to the dev plan's Phase 2 exit criteria, fixture scope)

1. `make db-up migrate seed && make snapshot && make match` → every fixture row leaves `pending`; statuses distribute across accept/review/reject; re-running `make match` is a no-op; a `match_runs` row exists.
2. `make evaluate-fixtures` passes ≥95/≥70/≥85 on the fixture corpus; pytest proves no planted trap is auto-accepted and `v1|fx-balenciaga-city-007|0` attributes to "Le City reissue".
3. Rematch with an injected rule change shifting one bag's matched set >15% → per-bag delta table printed, `match_runs.threshold_exceeded=true`; human-decided rows provably untouched.
4. Admin round-trip: login (wrong secret rejected, timing-safe at both layers) → dashboard shows snapshot runs/error counts → label 20 fixture listings keyboard-only → `make evaluate` reflects exactly those 20 → a review-queue approve flips the listing to `human_accepted` and creates an `origin=review_queue` gold label.
5. Broken fixture image URLs render the placeholder; `npm run lint:vocab`, `tsc --noEmit`, eslint, `next build` all green over the new admin surface.
6. CI green end-to-end: migrate → seed → pytest → snapshot ×2 → verify → **match → load fixture gold → evaluate --enforce** → retention dry-run.

## Defaults chosen (revisit at 2.6 with real data; none block)

Match state as `listings_raw` columns, traces regenerable (no history table) · provenance = two columns, first-fetch-wins · extractor keywords in code, aliases/exclusions in DB · weights 0.30/0.45/0.10×2cap/0.05/−0.60 tuned against the fixture harness · human decisions pinned during rematch · aggregate recompute deferred to 3.4 (delta logging ships now) · Next proxy + HMAC cookie over CORS/bearer-in-browser · plain `<img>` with error fallback · evaluation re-runs the matcher in memory rather than reading stored columns.
