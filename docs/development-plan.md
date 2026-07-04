# Covetability — Development Plan

## Context

Covetability is a market-intelligence platform for vintage designer handbags. The strategy phase is complete and settled (see `docs/decisions/architecture-decisions.md` ADR-001–007): v1 is an **honest active-market product** built on eBay Browse API asking data, a five-bag pilot, condition-banded pricing, and a gated Covetability Score v0 that runs in shadow mode before publication. eBay Marketplace Insights (sold data) is explicitly NOT a dependency.

This plan turns the four governing documents into an ordered build:

- `docs/product/data-contract.md` — binding metric definitions, display vocabulary, insufficient-data behavior
- `docs/product/covetability-score-v0.md` — score components, eligibility gates, stability tests, shadow-mode criteria
- `docs/data/canonical-catalog.md` — the 5 pilot bags with aliases, exclusions, misidentification traps
- `docs/decisions/architecture-decisions.md` — settled ADRs
- `design/prototype.html` — the working design prototype (Provenance/Covetability visual system, bag profile / variant / brand / signals / compare screens) to be translated into the Next.js frontend

**Constraints that shape the ordering:**
- **eBay API access is requested but not yet granted** → everything that needs live data has a fixture-replay fallback; non-API work is front-loaded.
- **Solo developer + Claude Code** → strictly ordered single track; each task sized to roughly one working session; no parallel workstreams assumed.
- **Stack (user-selected):** Python pipeline (FastAPI + workers) + Next.js frontend + Postgres. In-app admin routes.

**Definition of overall success:** the Chloé Paddington page renders real, condition-banded, honestly-labeled market data from ≥90 days of self-collected history, with a score whose every movement the operator can explain.

---

## Architecture overview

```text
covetability/
├── docs/                          # governing documents (exist)
├── pipeline/                      # Python: FastAPI + ingestion/matching/scoring
│   ├── pyproject.toml             # uv or poetry; ruff + pytest
│   ├── app/
│   │   ├── api/                   # FastAPI routers (public read API + admin API)
│   │   ├── models/                # SQLAlchemy models (mirror data-contract §5)
│   │   ├── ingestion/             # eBay Browse client, snapshot job, fixture replay
│   │   ├── matching/              # normalizer, matcher, exclusion engine
│   │   ├── conditions/            # condition-band normalizer
│   │   ├── aggregates/            # daily aggregate computation
│   │   ├── scoring/               # score v0 components, gates, shadow-mode log
│   │   └── settings.py
│   ├── alembic/                   # migrations
│   ├── jobs/                      # entrypoints run by scheduler (daily_snapshot.py …)
│   └── tests/
├── web/                           # Next.js (TypeScript, App Router)
│   ├── app/
│   │   ├── bags/[slug]/           # bag intelligence page
│   │   ├── discover/
│   │   └── admin/                 # labeling, match review, comps entry, score audit
│   └── lib/api.ts                 # typed client for pipeline API
└── infra/
    ├── docker-compose.yml         # local Postgres + pipeline
    └── .github/workflows/         # scheduled snapshot job (cron), CI
```

**Runtime decisions (defaults, revisit at Phase 7):**
- Postgres: local Docker for dev; hosted (Neon or Supabase, free tier) when jobs move to the cloud.
- Job scheduling: GitHub Actions scheduled workflow runs `jobs/daily_snapshot.py` daily (data volume for 5 bags is tiny; no VPS needed yet).
- Frontend deploy: Vercel. Pipeline API deploy: Railway or Fly (only needed once admin tools must be reachable away from the dev machine; until then FastAPI runs locally).
- Auth for admin: single shared secret in v0 (one operator), upgraded later.

---

## Phase 0 — Foundations (no eBay access needed)

**Goal:** repo, environments, database schema, and contract-enforcement fixtures exist; every later phase has rails to run on.

- [x] **0.1 Repo + scaffold.** `git init`; monorepo layout above; Python project (`uv init`, ruff, pytest), Next.js app (`create-next-app`, TypeScript, App Router); `docker-compose.yml` with Postgres 16; `.env.example` (DB URL, EBAY_APP_ID placeholder, ADMIN_SECRET). Commit the existing `docs/` and `index.html` (rename to `design/prototype.html` so it's clearly a reference artifact, not the app).
- [x] **0.2 Database schema, migration 001.** SQLAlchemy models + Alembic migration for the core tables:
  - `bag_models` (canonical identity: slug, brand, model, era, editorial fields)
  - `bag_aliases` (alias text, type: alias|misspelling|marketplace_term)
  - `bag_variants` (size/color-family level; `attribution_confidence` note per catalog doc)
  - `exclusion_terms` (global + per-bag, with `reason` category)
  - `listings_raw` (data-contract §4 provenance fields incl. `source_type`, `price_type`, `match_confidence`, `condition_raw/band/confidence`, `first_observed`, `last_observed`; **`expires_at` for the 90-day rolling window per ADR-003**)
  - `listing_events` (new / ended / possible_relist / repriced)
  - `daily_aggregates` (exactly data-contract §5: bag × variant-nullable × condition_band × day)
  - `manual_comps` (provenance-complete per data-contract §4; a DB constraint rejects rows missing source/date/condition)
  - `gold_labels` (listing ref, accept/reject, rejection-taxonomy enum from catalog doc, variant/size/color/condition/completeness labels)
  - `score_daily` (per bag: component values, eligibility flags, weights used, raw + smoothed score, confidence, `published` bool) — the shadow-mode log
- [x] **0.3 Data-contract enforcement fixtures.** Encode the contract as code early so it can't drift:
  - `pipeline/app/contract.py`: enums for condition bands, authentication labels (4-label taxonomy), rejection taxonomy; minimum-data constants (5 listings/band, 8 model-wide, 15 lifecycle events…).
  - `web/lib/vocabulary.ts`: display-string table (metric → allowed label) + a lint test that greps built pages for the prohibited vocabulary list (data-contract §6: "market value", "sell-through", bare "Authenticated"…). Failing string = failing CI.
- [x] **0.4 Seed script for the 5-bag catalog.** Parse-free approach: hand-transcribe `docs/data/canonical-catalog.md` into `pipeline/seeds/catalog.py` (brands, 5 models, aliases incl. unaccented forms, variants at the coarseness the doc specifies, global + per-bag exclusion terms with reasons). Idempotent `python -m seeds.catalog`.
- [x] **0.5 CI.** GitHub Actions: ruff + pytest on pipeline, tsc + eslint + vocabulary-lint on web, alembic upgrade check against a service Postgres.
- [x] **0.6 eBay account tracking task.** While access is pending: create the keyset request checklist (Browse API scope, production keyset, EPN application separately per ADR-001/007). Record status in `docs/decisions/` when granted. **Nothing else in Phase 0–1 blocks on this.**

**Phase 0 verification:** `docker compose up` + `alembic upgrade head` + seed script yields a Postgres with 5 bags, ~40 aliases, exclusion terms; CI green including the vocabulary lint; FastAPI `/health` and Next.js splash page run locally.

---

## Phase 1 — Ingestion (fixture-first, eBay-ready)

**Goal:** the daily snapshot pipeline runs end-to-end against recorded fixtures today, and flips to live eBay with a config change the day keys arrive.

- [x] **1.1 eBay Browse API client.** `pipeline/app/ingestion/ebay.py`: OAuth client-credentials flow, `search` (keyword + category filter + pagination) and `get_item` wrappers, rate-limit respect, typed response models (pydantic). Every request/response serializable to disk.
- [x] **1.2 Fixture-replay source.** Same interface as the live client, reading recorded JSON from `pipeline/fixtures/ebay/`. Until keys arrive, hand-build ~30 realistic fixture listings per pilot bag (real titles copied from public eBay search pages during manual research — titles/prices only, for dev fixtures) including known trap cases from the catalog doc: Paddington Bear merch, Balenciaga First mislabeled City, equestrian saddles, LV chain-strap accessories, replicas with "inspired" phrasing. **These fixtures double as the matcher's first test corpus.**
- [x] **1.3 Snapshot job.** `jobs/daily_snapshot.py`: for each bag's `initial_queries` (from catalog seed) → fetch → upsert `listings_raw` (first_observed/last_observed) → emit `listing_events` (new listing; listing absent from results N days → `ended` candidate) → write a `snapshot_runs` log row (counts per bag, errors). Idempotent per day.
- [x] **1.4 Retention job.** `jobs/expire_raw.py`: delete/blank `listings_raw` rows past `expires_at` (ADR-003) **after verifying the day's aggregates exist**. Test proves aggregates survive raw deletion.
- [x] **1.5 Scheduler.** GitHub Actions workflow with `schedule:` cron for both jobs against hosted Postgres — created but disabled until live keys; locally, jobs run via `make snapshot`.
- [ ] **1.6 [WAIT-GATE] Live smoke test.** When eBay grants access: run snapshot against production Browse API for one bag (Paddington), verify volume (expect 200–600 raw candidates), inspect rate-limit headroom, enable the scheduled workflow. **From this day the moat clock runs — this task has calendar priority over everything else in flight.**

**Phase 1 verification:** `make snapshot EBAY_SOURCE=fixtures` populates `listings_raw` + `listing_events` for all 5 bags; re-running is idempotent; a fixture listing removed from the fixture set produces an `ended` event; retention job deletes expired raw rows without touching aggregates.

---

## Phase 2 — Matching engine + gold-set tooling

**Goal:** listings are matched to canonical bags at measured precision; the labeling workflow that proves it exists. This phase is the actual pilot experiment (ADR-002).

- [x] **2.1 Title normalizer.** Lowercase, de-accent, punctuation strip, brand-token detection, size/color/material extractors (regex + keyword tables per catalog doc). Unit tests from fixture titles.
- [x] **2.2 Rule-based matcher v1.** Per listing: brand detect → alias match → exclusion-term scan (global + per-bag, each hit recorded with its reason category) → size/variant extraction → confidence score (weighted rule hits). Output: `(bag_model_id, variant_id?, confidence, rule_trace)` — the trace stored for the review UI. Thresholds from score-spec: ≥0.90 auto-accept, 0.60–0.90 review queue, <0.60 auto-reject.
- [x] **2.3 Admin shell + auth.** `web/app/admin/` layout, shared-secret login, nav. First screen: ingestion dashboard (snapshot runs, counts, error rates).
- [x] **2.4 Gold-set labeling UI.** Admin screen: one candidate listing at a time (title, price, image when available, matcher's guess + rule trace) → operator labels accept/reject with rejection-taxonomy buttons; on accept: variant, color family, condition band, completeness checkboxes. Keyboard-driven (this is a 750–1000-listing grind; ergonomics matter). Writes `gold_labels`.
- [x] **2.5 Precision measurement harness.** `pipeline/app/matching/evaluate.py`: matcher vs. gold labels → model-level precision/recall, per-bag breakdown, false-positive category table (which rejection reasons leak through), confusion listing export. Target per ADR-002: **precision ≥95% model-level, recall ≥70%, variant attribution ≥85%**.
- [ ] **2.6 [WAIT-GATE, follows 1.6] Label the real gold set.** 150–200 real candidates per bag from live snapshots (fixtures don't count for the launch threshold). Iterate: measure → tune exclusion terms/aliases from the false-positive table → re-measure. **Matcher-change re-baseline rule** (score-spec §7): every tuning round recomputes historical matches; log the matched-set delta.
- [x] **2.7 Match review queue UI.** Admin screen for the 0.60–0.90 band: approve/reassign/reject with taxonomy; approved decisions feed back as additional gold labels.

**Phase 2 verification:** `evaluate.py` report on the fixture corpus first (expect the planted traps caught), then on the real gold set; phase exits only at ≥95%/≥70%/≥85% on real data. The labeling UI round-trips: label 20 listings, evaluation report reflects them.

---

## Phase 3 — Condition normalization, relist detection, daily aggregates

**Goal:** the durable asset (the daily per-condition-band aggregate table) is computed correctly and honestly.

- [x] **3.1 Condition normalizer.** Map raw marketplace condition + description keyword scan ("tarnish", "full set", "sticky", "cracked", "patina", completeness terms per bag from catalog doc) → 6-band scale + `condition_confidence` (indeterminate allowed). Store raw + normalized (data-contract §4). Gold-set condition labels are the test set; **target ≥85% with adjacent-band confusions as half-errors** (ADR-002).
- [x] **3.2 Relist detection.** Key: `seller_id + normalized_title + image perceptual hash` (pHash via `imagehash` on primary image; store hash at ingestion). Ended listing reappearing ≤14 days same seller → `possible_relist` event linking old/new rows. Measured against a hand-checked sample; **lifecycle stats stay internal until precision >90%** (data-contract §1.3).
- [x] **3.3 Aggregate computation.** `jobs/daily_aggregates.py` (chained after snapshot in the same workflow): per (bag × variant-nullable × band × day) compute exactly the data-contract §5 row — winsorized (2/98) medians and p25/p75, `median_total_price` where shipping known, counts, `average_match_confidence`. **Bands below 5 listings still get a row (counts recorded) but price fields NULL** — insufficient-data behavior starts in the schema, not the UI.
- [x] **3.4 Backfill + recompute tooling.** `jobs/recompute_aggregates.py --since` for matcher re-baselines (score-spec §7 "matcher change must never appear as a market event").
- [x] **3.5 Aggregate-quality dashboard.** Admin screen: per bag/band coverage heatmap (days × bands with data), listing-count trends, match-confidence trend, gap alarms (snapshot ran but a bag got 0 candidates → query broke).

**Phase 3 verification:** unit tests: winsorization, mix-shift guard fixture (add 3 Excellent listings, blended median moves but per-band medians don't), NULL-below-minimum. Integration: 14 days of fixture snapshots → 14 aggregate rows per bag with plausible movements; relist fixture (same seller, retitled, same image) produces `possible_relist` not `ended`.

---

## Phase 4 — Bag intelligence page (built early, per ADR-006)

**Goal:** the flagship page exists against early/sample data, validating that the data model supports the experience *before* months of history accumulate in the wrong shape.

- [ ] **4.1 Public read API.** FastAPI routes: `GET /bags`, `GET /bags/{slug}` (identity, variants, editorial), `GET /bags/{slug}/market` (condition-band ranges from `daily_aggregates`, honoring minimums → explicit `insufficient_data` markers in the payload), `GET /bags/{slug}/history` (aggregate time series), `GET /bags/{slug}/listings` (active matched ≥0.90, with authentication label + verdict fields). Response schemas mirror `contract.py` — the API physically cannot emit a blended median as the primary price.
- [ ] **4.2 Design-system translation.** Port the visual system from `design/prototype.html` into `web/` as components: palette/typography tokens (Cormorant Garamond / Hanken Grotesk / IBM Plex Mono, the #E7DECF/#B0623E/#2B2520 scheme), stat cards, chip, badge, sparkline + line chart (the prototype's SVG chart helper translates directly), score ring, listings table.
- [ ] **4.3 Bag page — information hierarchy per the settled spec.** `web/app/bags/[slug]/page.tsx`, sections in this order:
  1. **What should I pay** — condition-banded "Typical asking range" cards; bands under minimum render "Insufficient reliable data" (never borrowed values)
  2. **Covetability status** — until score publication: component panels only + "Not yet scored — tracking since [month]" (score-spec §8 option, adopted)
  3. **Why it's moving** — 3–5 observations generated only from stored metrics (explanation rules, data-contract §3); server-side template over metric records, no free-form AI in v0
  4. **Listings worth considering** — price, band, "≈ N% above typical asking for [band]" verdict chips (only when band minimums met AND match ≥0.90), 4-label authentication taxonomy, last-verified timestamp, outbound link
  5. **History** — charts from `daily_aggregates` (asking medians per band, active count); short-history states designed deliberately ("42 days of tracking")
  6. **Editorial** — the bag's story, variants, naming confusion (content in 4.5)
- [ ] **4.4 Variant panels.** Variant-level price/availability panels labeled "model-level score" and "colorway attribution is best-effort" per score-spec/catalog docs.
- [ ] **4.5 Editorial capsules.** Write 5 × 150–300 words (release context, why it mattered, revivals, naming confusion) into `bag_models` editorial fields via admin catalog editor (4.6). Draft with Claude, fact-check by hand — these carry SEO weight.
- [ ] **4.6 Catalog editor (admin).** CRUD for bags/aliases/variants/exclusions + editorial fields; alias/exclusion edits flag "recompute required" (wired to 3.4).
- [ ] **4.7 Site-wide honesty furniture.** Methodology page (score identity statement verbatim from score-spec §1), authentication disclosure (data-contract §2), "Tracking since" on every page; vocabulary-lint (0.3) runs against rendered pages in CI.

**Phase 4 verification:** With fixture data: Paddington page renders every section including at least one deliberately-thin band showing the insufficient state; vocabulary lint passes; verdict chips absent (not "N/A") where minimums unmet; Lighthouse pass for the editorial/SEO basics (meta, structured data for products).

---

## Phase 5 — Search signal + Score v0 in shadow mode

**Goal:** all five score components compute daily with eligibility gates; the score exists internally with an audit trail; nothing is public.

- [ ] **5.1 Trends ingestion.** `jobs/weekly_trends.py`: pull model-level series per bag (canonical + top alias query, fixed anchor term) via pytrends or manual-export ingestion if API instability demands (pytrends is unofficial — build the ingestion behind an interface so the source can swap; store only derived weekly points, consistent with not redistributing Google data). Overlapping-window stitching + anchor rescale per score-spec §3.
- [ ] **5.2 Search bucket classifier.** 8-week smoothed slope → 5-bucket classification; store weekly per bag with the inputs that produced it.
- [ ] **5.3 Component calculators.** `scoring/components.py`: S, I, P, T, B exactly per score-spec §3 — including P's circularity guards (within-band momentum, 14-day repricing rule, divergence check) and T's experimental flag.
- [ ] **5.4 Gate + redistribution engine.** `scoring/gates.py`: eligibility checks per score-spec §4.1, pro-rata redistribution respecting ceilings (overflow → I then B), <3 eligible components → unscored. Property-based tests (hypothesis): weights always sum to 100 or model unscored; P never exceeds 25.
- [ ] **5.5 Confidence + smoothing + thresholds.** Confidence function with caps (§5); 7-day EMA; 2-point publication threshold; direction from 30-day published slope.
- [ ] **5.6 Daily score job.** Chained after aggregates: compute → write `score_daily` with full component/gate/weight trace, `published=false`.
- [ ] **5.7 Score audit screen (admin).** Per bag: score timeline, component stack over time, gate-status history, day-over-day movement decomposition ("+2.4: search bucket up→strong-up (+1.9), inventory −3 listings (+0.5)"). **This screen is the shadow-mode instrument — every material move must be explainable from it alone.**
- [ ] **5.8 Stability-gate harness.** `scoring/stability.py`: the four tests from score-spec §6 (weekly-transition flip rate with slope-change exemption, pull reproducibility ≥20 trials, alias agreement, window robustness) producing a pass/fail report per bag → the documented weight decision for S.
- [ ] **5.9 [CALENDAR-GATE] Shadow-mode operation.** ≥30 days (target 60) of daily scores with a written explanation log for every ≥3-point smoothed move (kept in `docs/decisions/shadow-log.md`). Watch specifically for: thin-data volatility, seller repricing feedback, false scarcity from relist misses, condition-mix shifts, matcher-change artifacts.

**Phase 5 verification:** replay tests — synthetic component inputs produce hand-computed scores; each gate triggers on its crafted fixture (e.g., alias disagreement excludes S and caps confidence at 0.75); the audit screen decomposition sums to the actual day delta; stability harness produces a decision artifact on real Trends data.

---

## Phase 6 — Manual comps, auction anchors, cultural notes

**Goal:** the human-operated evidence channels exist with full provenance, feeding breadth (B) and the page's context sections.

- [ ] **6.1 Manual comp entry (admin).** Form enforcing data-contract §4: source, source_type, observed date, condition, sold_confirmed, price_type, shipping_included, URL, entered_by; DB constraint backs the validation. Weekly operating cadence documented (Terapeak reads where permitted, Vestiaire/Fashionphile observations).
- [ ] **6.2 Auction records.** Same form, `source_type=auction_record`; renders ONLY in a separate "Notable sales" page section — a test asserts auction rows never enter `daily_aggregates` or verdict math (data-contract §4).
- [ ] **6.3 Cultural-context notes (admin).** Weekly curated note per bag (the 0%-weight editorial layer, ADR-004); renders in "Why it's moving" as clearly-labeled context, excluded from score math by construction.
- [ ] **6.4 Breadth wiring.** B component counts distinct sources with valid observations ≤30 days (API + manual with provenance), log-scaled per score-spec §3.

**Phase 6 verification:** a comp missing condition is rejected at both form and DB layer; an auction record appears in Notable Sales and provably not in any aggregate row; adding a second source moves B from 20 → 45 next scoring run.

---

## Phase 7 — Public launch (5 bags, score still unpublished)

**Goal:** the site is public and useful on price intelligence + editorial alone; launch criteria are data-quality thresholds, not a date.

**Launch gate (all required):**
- ≥90 days of daily aggregates per pilot bag
- Matcher ≥95%/≥70%/≥85% on the real gold set (Phase 2 exit re-verified on current rules)
- Condition ≥85% (half-error adjacent rule)
- Vocabulary lint green; methodology + disclosure pages live

Tasks:
- [ ] **7.1 Discover page.** Three modules only (ADR/settled scope): Most Covetable placeholder becomes "Featured" until score publication, Rising Asking Interest, Under the Radar — all computable from aggregates without the composite score.
- [ ] **7.2 Catalog search.** Simple: brand/model/alias text match over the 5 (later 30) bags. No facet wall.
- [ ] **7.3 Production deploy.** Hosted Postgres (migrate from local), pipeline API to Railway/Fly, web to Vercel, GitHub Actions jobs pointed at prod DB, uptime + job-failure alerting (a failed snapshot day is a data-integrity event: alert → backfill procedure documented).
- [ ] **7.4 EPN affiliate links.** Outbound eBay links carry EPN tracking (revenue + the partnership posture from ADR-001). Affiliate disclosure page.
- [ ] **7.5 Legal pass.** Terms/privacy; confirm eBay API license compliance posture (retention window implemented in 1.4; display requirements—item location/seller attribution—checked against current Browse API policy).
- [ ] **7.6 Analytics.** Privacy-light analytics (Plausible or similar): the metric that matters is bag-page depth + outbound clicks (the "screenshot moment" proxy).

**Phase 7 verification:** production smoke: a full scheduled day (snapshot → aggregates → score-shadow) runs unattended in prod; the public Paddington page shows live data; a deliberate job failure triggers the alert; EPN link resolves with tracking intact.

---

## Phase 8 — Score publication + catalog expansion

**Goal:** publish the score once shadow-mode criteria hold in production; grow to 30 bags without diluting quality.

- [ ] **8.1 Score publication review.** Score-spec §8 checklist against the production shadow log; stability-gate decision applied (S at 15/25/30%); flip `published=true` pathway + the full score UI (ring, classification, confidence, component breakdown with greyed-out ineligibles, tracking-since).
- [ ] **8.2 "Why it's moving" upgrade.** Explanations driven by published-score decomposition (still template-over-metrics; AI rephrasing only if it passes the explanation rules and adds nothing not in the metric record).
- [ ] **8.3 Expansion playbook.** Document the per-bag onboarding recipe proven by the pilot: catalog entry → queries → 150-label gold sample → precision check → 2 weeks ingestion → page live. Expand in waves of ~5 (next wave from the spec's suggested set: Speedy, Jackie, Re-Edition, Spy, Stam), each wave passing the same thresholds. 30 bags ≈ 5 waves.
- [ ] **8.4 Deferred-scope trigger review.** Only after score publication + first expansion wave: revisit ADR-007 deferrals (Covet List, alerts) — first candidate is per-bag "watch" with a weekly email digest, smallest honest personalization.

**Phase 8 verification:** score visible publicly with confidence + tracking-since; one full expansion wave onboarded via the playbook meeting all thresholds; shadow log archived as the methodology audit trail.

---

## Sequencing summary (solo track)

```text
Phase 0  Foundations                          ~4-6 sessions   no eBay needed
Phase 1  Ingestion (fixtures)                 ~4 sessions     1.6 waits on eBay keys
Phase 2  Matching + gold tooling              ~6-8 sessions   2.6 waits on live data
Phase 3  Conditions + aggregates              ~5 sessions     fixture-testable
Phase 4  Bag page + editorial                 ~6-8 sessions   fixture-renderable
Phase 5  Score shadow mode                    ~6 sessions     + ≥30-60 day calendar gate
Phase 6  Manual evidence channels             ~3 sessions
Phase 7  Public launch                        ~4-5 sessions   gated on 90d data + thresholds
Phase 8  Score publication + expansion        ongoing
```

Critical path while waiting for eBay: 0 → 1(fixtures) → 2.1–2.5 → 3 → 4 — the entire system is buildable and testable on fixtures. The moment keys arrive, run 1.6 (start the moat clock), then 2.6 labeling becomes the dominant human task. Calendar gates (90-day history, 30–60-day shadow mode) overlap with build phases 4–6, so waiting time is absorbed, not idle.

## Verification strategy (cross-cutting)

- **Contract-as-code:** `contract.py` + `vocabulary.ts` lint make data-contract violations CI failures, not review comments.
- **Fixtures with planted traps:** the catalog doc's misidentification cases are permanent regression tests.
- **Every phase has an exit criterion that is a measurement, not a feeling** (precision %, coverage days, explainability log completeness).
- **End-to-end check per phase** listed above; the standing e2e is: one simulated day (snapshot → match → aggregate → score) on fixtures completes in CI.

## Risks / open items

| Risk | Mitigation in plan |
|---|---|
| eBay production access delayed further | Fixture-first Phases 0–4; only 1.6/2.6 and calendar gates block on it |
| pytrends instability (unofficial API) | Ingestion behind an interface (5.1); manual-export fallback; S component is gated anyway |
| Solo-operator labeling fatigue (~1000 labels) | Keyboard-first UI (2.4); labels amortized: review-queue decisions keep feeding the gold set |
| Image pHash needs image bytes within license terms | Compute hash at ingestion, store hash not image; verify in 7.5 legal pass |
| GitHub Actions cron jitter for daily jobs | Snapshot job is idempotent per-day; alerting catches missed days; move to a real scheduler if it recurs |
| Score never passes shadow criteria | Acceptable outcome by design — site launches and is useful without the composite (Phase 7 precedes 8) |
