# Phase 4 Implementation Plan

Phase 4 builds the first public bag intelligence page against fixture-backed aggregates, plus the catalog editor needed to keep the catalog maintainable before longer history accumulates.

## Scope

- Add public read APIs for bag identity, market ranges, history, and active listings.
- Serve market data from `daily_aggregates`; do not recompute public ranges from raw listings.
- Enforce insufficient-data price omission in API schemas.
- Keep score output pre-publication: "Not yet scored - tracking since [month]".
- Add deterministic, templated market observations from aggregates only.
- Build the public bag page, methodology page, shared public components, JSON-LD without offers, sitemap, and robots.
- Add catalog CRUD/admin editing with recompute-required flagging and CLI-only clearing through aggregate recompute.
- Seed editorial capsules fill-if-null so fixture pages render useful prose from day one.

## Binding Decisions

- Public API lives in `app/api/public/` and mounts unauthenticated at root.
- Next server components fetch through `PIPELINE_API_URL`, so no CORS changes are needed.
- `/market` has no top-level blended price field; all prices are per condition band and per separate-market variant band.
- Listing verdicts are computed server-side only for eligible accepted USD listings with enough band data, auto-accept confidence, and a non-indeterminate condition.
- Listing turnover remains internal for v0; public history exposes active and new listing activity only.
- Auth labels use the stored database value, with ingestion mapping eBay `AUTHENTICITY_GUARANTEE` to `marketplace_authentication_program`.
- Recompute UX is a banner with a concrete CLI command; APIs never execute recompute jobs.
- `recompute_required` is cleared only by `jobs/recompute_aggregates.py` after a successful recompute.

## Verification Targets

- Public API pytest coverage for no-auth access, 404s, schema field shape, insufficient bands, verdict eligibility, active filtering, and listing ordering.
- Observation pytest coverage for exact templated sentences, ordering, caps, and thin-band exclusion.
- Admin catalog pytest coverage for recompute flag behavior and variant deletion safeguards.
- Editorial seed tests for word count and banned vocabulary.
- Web checks: `npm run lint:vocab`, `npx tsc --noEmit`, `npm run lint`, and `npm run build`.
- Fixture chain: migrate, seed, snapshot, match, normalize conditions, aggregate, then public API/page smoke.
