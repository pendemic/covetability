# Phase 7 - Public launch (5 bags, score still unpublished)

## Context

Phase 7 makes the site public and useful on price intelligence + editorial alone; the composite score stays in shadow mode. The launch trigger is data-quality thresholds, not a date.

**Before any Phase 7 work can start, Phase 5 and Phase 6 must be reconciled onto one line.** They were built on divergent branches and currently conflict:

- **Phase 5** (score shadow engine: `app/trends/`, `app/scoring/{components,compute,gates,confidence,smoothing,stability,price_guard,util}.py`, `search_signal_weekly`/`score_price_points`/`trend_pulls`/`score_runs`, admin score audit screen) lives on `claude/dev-phases-1-5-review-wi76tx` and adds migration **`006_score_shadow`** (`down_revision = 005_catalog_editor`).
- **Phase 6** (manual comps, auction anchors, cultural notes: `app/api/{admin,public}/evidence.py`, `app/scoring/breadth.py`, `cultural_notes`, provenance constraints, admin evidence page, bag-page context sections) landed on `master` and adds migration **`006_manual_evidence`** (`down_revision = 005_catalog_editor`).

So `master` has Phase 6 but is **missing the entire Phase 5 scoring engine**, and there are **two different migration `006` files, both chained off `005`** - an alembic multiple-heads conflict. Phase 7's launch verification ("a full scheduled day snapshot -> aggregates -> score-shadow runs unattended in prod") depends on both being present. Reconciliation is therefore Phase 7's step 1, not an afterthought.

## Prerequisite: integrate Phase 5 + Phase 6

Produce one integrated baseline (merge the branches, or replay Phase 5 onto `master`) with:

- **Linearized migrations.** Keep `006_manual_evidence` as-is; renumber the Phase 5 migration to **`007_score_shadow`** with `down_revision = "006_manual_evidence"`. Phase 7's own migration becomes `008_launch`. Verify `alembic heads` reports a single head and `upgrade head` + full downgrade roundtrips.
- **One breadth implementation.** Phase 6's `scoring/breadth.py::marketplace_breadth` correctly excludes `auction_record`; Phase 5's `components.py::compute_breadth` does **not** (it counts every manual source - a latent bug). Unify on the auction-excluding logic: have the score compute call `marketplace_breadth` (or fold its `source_type != auction_record` filter into `compute_breadth`) and delete the duplicate. Add the `user_submitted` exclusion too (no channel exists yet, ADR-007).
- **Merge-conflict resolution** in the files both phases touched: `app/api/admin/__init__.py` (score + evidence routers), `app/models/__init__.py` (score + `CulturalNote` exports), `web/lib/{adminApi,adminVocabulary}.ts`, `web/app/admin/(app)/layout.tsx` (both nav links), and the `docs/development-plan.md` checkbox block (5.1-5.8 and 6.1-6.4).
- **Two contract fixes surfaced in the Phase 6 review** (fold in here):
  1. The public heading `notableSales: "Notable sales"` uses "sales", which data-contract §6 prohibits site-wide (ADR-005 makes §6 binding). It only passes CI because `vocab-lint` allowlists `lib/vocabulary.ts` and callers reference the key, not the literal - a mechanical gap, not a clean pass. Rename to **"Notable auction results"** (route `/auction-records` already avoids it) so the copy honors §6, and keep the auction section clearly separated from asking data.
  2. Add the missing `sold_confirmed => auction_record` DB CHECK (data-contract §4: `sold_confirmed` is true ONLY for auction records) so no non-auction path can flag a row as confirmed.

**Exit:** the integrated tree is green (ruff, full pytest incl. both phases' suites, migrate/seed, e2e pipeline snapshot -> match -> conditions -> aggregates -> trends -> daily_score with evidence present, web tsc/eslint/vocab/build); one simulated day runs end to end; `score_daily.published` stays false.

## Decisions

- **Nothing public depends on the composite score.** Discover and the bag page compute entirely from `daily_aggregates` (+ editorial + evidence). The score stays shadow-only until Phase 8, so every Phase 7 surface must render honestly with the score absent.
- **The launch trigger is the data-quality gate below, not a calendar date.** Phase 7 *build* is fixture-renderable now; the *launch* waits on real history and the still-open WAIT-GATEs (1.6/2.6 on eBay keys, 5.9 shadow calendar).
- **EPN wrapping is server-side and config-gated.** Outbound eBay `item_url`s are wrapped through an `epn_wrap` helper gated on an `EPN_CAMPAIGN_ID` setting (raw URL passthrough when unset, so fixtures/dev are unaffected). Every outbound link carries the affiliate posture from ADR-001; an affiliate-disclosure page and an inline disclosure near outbound links satisfy FTC + eBay Partner Network terms.
- **Analytics is privacy-light and CSP-safe.** A single self-hostable analytics include (Plausible-style) measures the two metrics that matter - bag-page depth and outbound clicks (the "screenshot moment" proxy) - with no PII and no cross-site cookies.
- **Deploy topology matches the dev-plan defaults:** hosted Postgres (Neon/Supabase free tier), pipeline API to Railway/Fly, web to Vercel, GitHub Actions jobs (`snapshot.yml`, `trends.yml`) pointed at the prod DB. A failed snapshot/score day is a data-integrity event: it alerts and has a documented backfill procedure.

## Launch gate (all required, restated with current mechanisms)

- >= 90 days of `daily_aggregates` per pilot bag (real, self-collected; starts at WAIT-GATE 1.6).
- Matcher >= 95% / >= 70% / >= 85% on the **real** gold set (`evaluate_matcher --enforce`, re-verified on current rules; WAIT-GATE 2.6).
- Condition accuracy >= 85% with the adjacent-band half-error rule (`evaluate_conditions --enforce`).
- `vocab-lint` green (including the "Notable auction results" fix); methodology + authentication-disclosure + affiliate-disclosure pages live.

## Design

Migration `008_launch` is small: optional discover/search support indexes if query plans need them (e.g. a trigram or `lower()` index on `bag_models.model_name`/`bag_aliases.alias` for search) plus any settings-backed columns; most of Phase 7 is API + web + ops, not schema.

Public read path: a new `app/api/public/discover.py` exposing `GET /discover` with exactly three modules computed from `daily_aggregates` (no composite score): **Featured** (curated/editorial standin for "Most Covetable" until score publication), **Rising asking interest** (largest 30-day rise in blended asking median or active matched count), **Under the radar** (thin active inventory / low coverage). A `GET /bags?q=` (or `app/api/public/search.py`) does brand/model/alias substring match over the 5 (later 30) bags - no facet wall. Schemas in `app/api/public/schemas.py`.

EPN: `app/api/public/epn.py` (or a helper in `listings.py`) wraps `item_url` via the eBay rover/EPN pattern using `EPN_CAMPAIGN_ID` from `settings.py`; `bag_listings` serialization returns the wrapped URL. Outbound clicks are the tracked conversion.

Web: `web/app/discover/page.tsx` (three modules), a catalog search box on the home/discover pages, an affiliate-disclosure page and a terms/privacy page under `web/app/`, EPN/disclosure surfacing in `ListingsTable` (MarketComponents), and the analytics include in `web/app/layout.tsx`. Item location + seller attribution surfaced on listings to meet eBay Browse display requirements (7.5).

Ops: `docs/runbooks/production-deploy.md` (hosted Postgres migration, API + web deploy, secrets, pointing jobs at prod) and `docs/runbooks/job-failure-backfill.md` (alerting + backfill). Job-failure alerting reads `snapshot_runs` / `aggregate_runs` / `score_runs` status and notifies on a failed or missed day.

## Build order

1. **Integration + reconciliation** (the prerequisite above): linearize migrations to `007_score_shadow`, unify breadth, resolve merge conflicts, apply the two contract fixes, get the combined tree fully green.
2. **7.2 Catalog search.** `/bags?q=` brand/model/alias substring match; migration `008_launch` index if needed; home/discover search box; tests.
3. **7.1 Discover page.** `/discover` three-module API from aggregates + `web/app/discover/page.tsx`; "Featured" is the score-free placeholder until Phase 8; tests assert modules compute without the composite score and honor insufficient-data.
4. **7.4 EPN affiliate links.** `epn_wrap` + `EPN_CAMPAIGN_ID` setting; wrapped outbound URLs; affiliate-disclosure page + inline disclosure; test that links carry tracking when configured and pass through untouched when not.
5. **7.5 Legal pass.** Terms/privacy pages; eBay Browse display compliance (item location + seller attribution on listings); confirm the 90-day retention posture (already in `jobs/expire_raw.py`); affiliate disclosure linked site-wide.
6. **7.6 Analytics.** Privacy-light analytics include (bag-page depth + outbound clicks); no PII; CSP-safe; documented events.
7. **7.3 Production deploy.** Hosted Postgres migration + seed; pipeline API to Railway/Fly; web to Vercel; jobs pointed at prod DB; uptime + job-failure alerting; deploy + backfill runbooks. Production smoke: a full scheduled day (snapshot -> aggregates -> score-shadow) runs unattended; a deliberate job failure fires the alert.
8. **Docs + verification sweep.** Check off dev-plan 7.1-7.6; confirm the launch gate mechanisms; full local CI-equivalent; commit + push.

## Verification

- Combined tree: single alembic head, `upgrade head` + downgrade roundtrip clean; full pytest (Phase 5 + 6 + 7 suites) green; one simulated day runs snapshot -> ... -> score-shadow with evidence present and `published=false`.
- Breadth counts `api` + `manual` sources only; an `auction_record` source never moves B; a second `manual` source moves B 20 -> 45 (the Phase 6 test still passes against the unified compute).
- Discover returns exactly three modules, all computed without the composite score; thin bags render insufficient-data honestly, not borrowed values.
- Catalog search matches by brand/model/alias and returns nothing prohibited.
- Outbound eBay links carry EPN tracking when `EPN_CAMPAIGN_ID` is set and are unchanged when it is not; the affiliate disclosure is reachable from every outbound context.
- `vocab-lint` green with "Notable auction results"; methodology + authentication + affiliate disclosures live; Lighthouse SEO basics (meta, product structured data) pass on discover + bag pages.
- Production smoke: a full unattended scheduled day in prod; a deliberate job failure triggers the alert; an EPN link resolves with tracking intact.

## Key files

New: `pipeline/alembic/versions/008_launch.py`, `pipeline/app/api/public/{discover,search,epn}.py`, `web/app/discover/page.tsx`, `web/app/affiliate-disclosure/page.tsx`, `web/app/terms/page.tsx`, `web/app/privacy/page.tsx`, `pipeline/tests/test_{discover_api,search_api,epn_links}.py`, `docs/runbooks/{production-deploy,job-failure-backfill}.md`.

Changed (integration + Phase 7): renamed `006_score_shadow.py` -> `007_score_shadow.py`; `pipeline/app/scoring/{components,compute}.py` (single breadth path); `pipeline/app/api/public/{__init__,listings,schemas}.py`; `pipeline/app/settings.py` (`EPN_CAMPAIGN_ID`, analytics config); `pipeline/app/models/market.py` (`sold_confirmed => auction_record` CHECK, via migration `008`); `web/lib/{publicApi,vocabulary}.ts` (rename "Notable sales" -> "Notable auction results"); `web/app/components/MarketComponents.tsx`; `web/app/layout.tsx` (analytics); `web/app/page.tsx` (search + discover entry); `docs/development-plan.md`.

## Accepted risks

- **Integration debt is the real cost here.** Two phases built in parallel means a genuine merge with a migration renumber and a breadth de-dup; skipping it produces a broken alembic history in prod. The plan front-loads it as step 1 with an explicit green-tree exit.
- **Launch is data-gated, not build-gated.** Phase 7 can be fully built on fixtures, but going public waits on >= 90 days of real aggregates and the matcher/condition thresholds on the real gold set - i.e. on eBay keys (1.6/2.6). Do not conflate "Phase 7 done" with "launched."
- **EPN + license compliance.** eBay Browse display requirements (item location, seller attribution) and EPN disclosure are checked in 7.5 before any public outbound link ships; retention (90 days) is already enforced.
- **The score is still absent in public.** Every Phase 7 surface must be useful and honest with no composite number; the "Featured" module and score panels are deliberate placeholders until Phase 8 publication.
```
