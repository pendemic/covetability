# Phase 0 — Foundations (implementation plan)

## Context

The strategy docs and the phased development plan are committed (`docs/development-plan.md`, governed by `docs/product/data-contract.md`, `docs/product/covetability-score-v0.md`, `docs/data/canonical-catalog.md`, `docs/decisions/architecture-decisions.md`). This plan executes **Phase 0 — Foundations** exactly as specified there: repo scaffold, database schema, contract-as-code, 5-bag seed, and CI. No eBay access is needed for any of it. The outcome is a running skeleton (Postgres + FastAPI + Next.js) with the data contract enforced by code and the pilot catalog seeded, so Phase 1 (fixture ingestion) has rails to run on.

Environment check done: Docker 29 + Compose v5, Node 22, Python 3.11, uv 0.8, psql 16 all present.

## 0.1 Repo scaffold

Target layout (from development-plan "Architecture overview"):

```
pipeline/         # Python: uv project — FastAPI, SQLAlchemy 2.0, Alembic, pydantic-settings, ruff, pytest
  app/{api,models,ingestion,matching,conditions,aggregates,scoring}/   # packages created empty except where Phase 0 fills them
  app/contract.py  app/settings.py
  alembic/         seeds/catalog.py    jobs/    tests/
web/              # create-next-app: TypeScript, App Router, ESLint; lib/vocabulary.ts
infra/docker-compose.yml   # postgres:16, volume, healthcheck
design/prototype.html      # git mv index.html design/prototype.html (reference artifact, not the app)
.env.example      # DATABASE_URL, EBAY_APP_ID/CERT_ID placeholders, ADMIN_SECRET
Makefile          # make db-up, migrate, seed, test, lint
.github/workflows/ci.yml
```

- `pipeline`: `uv init`, deps: `fastapi uvicorn sqlalchemy alembic psycopg[binary] pydantic-settings`; dev: `ruff pytest`. Minimal FastAPI app with `GET /health`.
- `web`: `create-next-app` (TS, App Router, ESLint, no Tailwind decision forced — accept default), splash page only.
- `app/settings.py`: pydantic-settings reading `DATABASE_URL`, `ADMIN_SECRET`, `EBAY_*`.

## 0.2 Database schema — migration 001

SQLAlchemy 2.0 models in `pipeline/app/models/` + one Alembic migration. Tables (fields per data-contract §4/§5 and dev-plan 0.2):

- `brands`, `bag_models` (slug, brand FK, model name, era, editorial fields as nullable text, `initial_queries` JSONB — needed by Phase 1 snapshot job, `tracking_since` date)
- `bag_aliases` (bag FK, alias, type enum: alias | misspelling | marketplace_term)
- `bag_variants` (bag FK, name, kind: size | color_family | edition, `attribution_confidence` note, `is_separate_market` flag for splits like Le City reissue / Saddle vintage-vs-modern / Pochette NM)
- `exclusion_terms` (term, scope: global | bag FK nullable, reason category)
- `listings_raw` — provenance-complete per data-contract §4: source, source_type, marketplace item id, title, price, currency, shipping fields, seller id, item URL, image pHash placeholder column, `price_type`, `match_confidence`, matched bag/variant FKs nullable, `condition_raw/band/confidence`, auth-label enum, `first_observed`, `last_observed`, **`expires_at`** (90-day rolling window, ADR-003)
- `listing_events` (listing FK, type: new | ended | possible_relist | repriced, event_date, payload JSONB)
- `daily_aggregates` — **exactly data-contract §5**, unique on (bag, variant-nullable, band, date); price columns nullable (insufficient-data lives in the schema)
- `manual_comps` — CHECK constraints reject rows missing source, observed_at, or condition (data-contract §4 rule)
- `gold_labels` (listing ref, verdict accept/reject, rejection-taxonomy enum, and on accept: variant, color family, condition band, completeness booleans strap/lock/key/dustbag/cards)
- `score_daily` (bag, date, per-component value + eligibility flag + weight used, raw score, smoothed score, confidence_raw, `published` bool default false, notes) — the shadow-mode log

## 0.3 Contract-as-code

- `pipeline/app/contract.py`: enums — `ConditionBand` (6 bands, named by the product spec §10: **new_or_unused, excellent, very_good, good, fair, poor**; recorded as ADR-008 as part of this task), `ConditionConfidence` (incl. indeterminate), `AuthLabel` (4-label taxonomy, data-contract §2), `RejectionReason` (10 categories, catalog gold-set section), `SourceType`, `PriceType`, `ScoreClassification` (Dormant…Surging with bounds).
  Constants: `MIN_LISTINGS_PER_BAND=5`, `MIN_MODEL_WIDE_LISTINGS=8`, `MIN_LIFECYCLE_EVENTS=15`, `MATCH_AUTO_ACCEPT=0.90`, `MATCH_REVIEW_FLOOR=0.60`, `WINSOR_PCT=(2,98)`, `RAW_RETENTION_DAYS=90`, `RELIST_WINDOW_DAYS=14`, score base weights/ceilings, confidence caps (score-spec §5). DB enums in 0.2 import from here — one source of truth.
- `web/lib/vocabulary.ts`: metric → allowed display-string table plus the prohibited list (data-contract §6: "market value", "worth", "valuation", "sold", "sell-through", "sales rate", bare "Authenticated", "demand", "investment", "appreciating", "ROI", "forecast", "prediction").
- **Vocabulary lint**: node script `web/scripts/vocab-lint.mjs` scanning `web/app` + `web/lib` source (and later, built output) for prohibited strings, with an allowlist mechanism for the vocabulary file itself; wired as `npm run lint:vocab` and into CI. Failing string = failing CI.
- Python-side guard: a pytest that asserts `daily_aggregates` model has no column or property named like the prohibited terms and that `contract.py` constants match data-contract numbers (change-detector test with doc references).

## 0.4 Seed script — 5-bag catalog

`pipeline/seeds/catalog.py`, idempotent upsert by slug (`python -m seeds.catalog`). Hand-transcribed from `docs/data/canonical-catalog.md`:

- 5 brands, 5 models (Paddington, City, Baguette, Saddle, Pochette Accessoires) with era, `initial_queries`, expected-range notes in editorial stub.
- Aliases including unaccented forms ("chloe paddington"), misspellings ("Pochette Accessories"), marketplace terms (Trotter, Moto/Motorcycle Bag, Zucca…).
- Variants at the doc's coarseness — incl. the mandated splits: Le City reissue, Saddle vintage/modern, Baguette re-edition, Pochette NM; separate-model exclusions (First/Town/Work/Part-Time, Mini Pochette) go to **exclusion terms**, not variants.
- Global exclusion list (replica, inspired, dupe, "dust bag only", charm, …) + per-bag negative keywords (Paddington Bear/marmalade, equestrian/western, Mama Forever/croissant, Félicie/Métis/insert/organizer…), each with a reason category.

## 0.5 CI — `.github/workflows/ci.yml`

- **pipeline job**: postgres:16 service → `uv sync` → `ruff check` → `alembic upgrade head` → seed script → `pytest`.
- **web job**: `npm ci` → `tsc --noEmit` → `next lint` → `npm run lint:vocab`.

## 0.6 eBay access tracking

`docs/decisions/ebay-access.md`: keyset request checklist (Browse API scope, production keyset, EPN application separately per ADR-001/007), status = pending. Nothing else blocks on it.

## Files created/modified (key ones)

- New: `pipeline/**` (pyproject, app/, alembic/, seeds/, tests/), `web/**`, `infra/docker-compose.yml`, `Makefile`, `.env.example`, `.github/workflows/ci.yml`, `docs/decisions/ebay-access.md`
- Modified: `docs/development-plan.md` (tick Phase 0 checkboxes), `docs/decisions/architecture-decisions.md` (ADR-008: condition-band names per product spec §10)
- Moved: `index.html` → `design/prototype.html`

## Verification (Phase 0 exit criteria, from the dev plan)

1. `docker compose -f infra/docker-compose.yml up -d` → healthy Postgres.
2. `alembic upgrade head` then `python -m seeds.catalog` → psql spot-check: 5 bags, ~40 aliases, global + per-bag exclusion terms; re-run seed → no duplicates (idempotent).
3. `pytest` green — includes: manual_comps constraint rejects a row missing condition; daily_aggregates uniqueness; contract constants test.
4. `uvicorn` up → `GET /health` 200; `npm run dev` → splash renders.
5. `npm run lint:vocab` passes; then plant "market value" in a page, confirm it fails, remove it.
6. Commit (Phase 0 as one commit or a small series; no push/PR unless asked).

Out of scope this session (next up, Phase 1): eBay client, fixture corpus, snapshot/retention jobs.
