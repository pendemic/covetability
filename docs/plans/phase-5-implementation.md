# Phase 5 - Search signal + Score v0 in shadow mode

## Context

Phases 0-4 are committed: schema through migration 005, contract-as-code, fixture-first ingestion, matching, condition normalization, daily aggregates, the public bag page, and the admin catalog editor. Phase 5 makes all five score components compute daily with eligibility gates so the Covetability Score exists internally with a full audit trail. Nothing public changes in this phase: public bag pages continue to show "Not yet scored - tracking since [month]" while `score_daily.published` remains false.

The `score_daily` table and score constants already exist from Phase 0: base weights, ceilings, confidence weights and caps, classification bounds, and minimum data thresholds. Phase 5 adds the missing signal stores, scoring jobs, audit trace, stability harness, and admin shadow-mode instrument.

## Decisions

- Trends source is selectable by `TRENDS_SOURCE=fixtures|pytrends|csv`, mirroring the existing `EBAY_SOURCE` pattern. pytrends is primary for live collection, CSV is the manual fallback, and fixtures drive CI.
- pytrends is an optional dependency group so live trends fragility cannot block CI. The CSV importer reads Google Trends UI `multiTimeline.csv` exports.
- Trends pulls are append-only. Every pull/import writes a `trend_pulls` row with bag, query role, source, window, anchor-rescaled weekly points JSONB, and a low-volume flag. Repeated same-window pulls accumulate for the stability gate's reproducibility test.
- Stitched weekly search signal is stored separately in `search_signal_weekly` per bag and week. It stores the stitched canonical value, 8-week and 4-week slopes, bucket, alias-direction agreement, low-volume flag, series length, and input trace.
- Price momentum is computed from a scoring-internal guarded price series, not directly from `daily_aggregates`, because the score spec's 14-day same-seller repricing rule cannot be applied after aggregate medians are already computed.
- `score_price_points` persists per bag, condition band, and day the guarded winsorized median used for scoring. Persisting this series lets the 90-day price slope survive raw-row expiry.
- Mix-adjustment weights are fixed in `contract.py` and renormalized over bands meeting the minimum so a condition-mix shift toward Excellent cannot read as a price rise.
- Inventory momentum reads `daily_aggregates`: model-level active count is the sum of active listing counts across variant-NULL and separate-market variant rows, then smoothed with a 7-day rolling window and mapped through a provisional ladder.
- Turnover reads `listing_events` but launches ineligible by default with reason `relist precision unvalidated`. The component is gated on `MIN_LIFECYCLE_EVENTS` and relist precision above 0.90 once a gold sample exists.
- Breadth counts distinct valid sources in the trailing 30 days from `listings_raw.source` and `manual_comps.source`, mapped through the score-spec ladder.
- All provisional scoring ladders and thresholds live in `contract.py` with comments marking them as tuned during shadow mode.
- Gates and weight redistribution are pure functions in `scoring/gates.py`. Eligibility flags plus base weights produce redistributed weights under ceilings; overflow goes to inventory, then breadth; fewer than three eligible components leaves the model unscored.
- Daily scoring runs in shadow. The job computes raw score, 7-day EMA, a shadow publication-track value that only moves on at least 2-point smoothed deltas, and a 30-day publication-track direction. `published` stays false in Phase 5.
- `component_trace` carries the complete per-day audit record: component inputs, values, eligibility reasons, weight used, redistribution steps, confidence factors and caps, EMA inputs, and publication-track inputs.
- The score job is idempotent per day using delete-then-insert semantics and appends a `score_runs` audit row.

## Design

Migration 006, `006_score_shadow.py`, adds scoring shadow-mode storage. New tables are `trend_pulls`, `search_signal_weekly`, `score_price_points`, and `score_runs`. New `score_daily` columns are `publication_value Numeric(6,2)`, `direction`, and `unscored_reason`. New enums are `search_bucket` (`strong_up`, `up`, `flat`, `down`, `strong_down`), `score_direction` (`rising`, `falling`, `stable`), and `trend_query_role` (`canonical`, `alias`).

The trends package lives in `pipeline/app/trends/`. `source.py` defines the source protocol and selection by `TRENDS_SOURCE`; `pytrends_source.py`, `csv_source.py`, and `fixtures.py` implement live, manual, and fixture sources. `stitch.py` performs overlapping-window stitching with fixed-anchor rescale. `classify.py` turns the 8-week smoothed slope into the five search buckets, computes alias agreement, and detects low volume.

The scoring package lives in `pipeline/app/scoring/`. `components.py` contains S/I/P/T/B component calculators returning `ComponentResult(value, eligible, reason, trace)`. `price_guard.py` builds the guarded price series and persists `score_price_points`. `gates.py` performs eligibility and redistribution. `confidence.py` computes confidence from the existing weights and applies caps. `smoothing.py` computes EMA, publication-track movement, and direction. `compute.py` orchestrates daily score writes. `stability.py` implements the four score-spec stability tests: flip rate with slope-change exemption, pull reproducibility, alias agreement, and window robustness.

Score components read from the following durable sources:

- S: `search_signal_weekly`, with bucket scores from `SEARCH_BUCKET_SCORES` and stability gates.
- I: `daily_aggregates` active counts, smoothed and mapped through a provisional ladder.
- P: `score_price_points`, using fixed condition-band mix weights and guarded repricing logic.
- T: `listing_events`, gated off until relist precision is validated.
- B: valid source count over the trailing 30 days across raw listings and manual comps.

Jobs follow the existing `python -m jobs.X` pattern. `weekly_trends` imports or pulls trends, writes `trend_pulls`, and stitches `search_signal_weekly`. `daily_score` computes one day of score rows and appends `score_runs`. `stability_report` runs the shadow stability harness and prints a per-bag pass/fail report plus the recommended search weight decision.

The admin audit surface lives in `pipeline/app/api/admin/score.py` and `web/app/admin/(app)/score/page.tsx`. Endpoints expose score timeline rows and traces, per-day decomposition, gate-status history, and weekly search-signal history. The web page is an internal shadow instrument with a bag selector, score/publication-track timeline, component stack, gate history, and day-over-day decomposition panel.

Fixtures live in `pipeline/fixtures/trends/<slug>.json` with at least 20 weeks per bag, canonical and top alias series, and planted gate cases: strong-up, alias disagreement, low volume, short series, and multi-pull jitter for reproducibility trials.

`docs/decisions/shadow-log.md` is the calendar-gate scaffold for Phase 5.9. It records real-data score moves, component decomposition, explanation, and operator verdicts before any public score publication.

## Build Order

1. Schema and constants: migration 006, new enums, score-run/trend/search/price models, provisional ladders in `contract.py`, and contract tests.
2. Trends ingestion: source protocol, pytrends optional source, CSV source, fixture source, pull audit rows, stitching, classification, fixture trends, `weekly_trends` job.
3. Component calculators: S/I/P/T/B calculators, guarded price series builder, source breadth, turnover default-ineligible behavior, and focused unit tests.
4. Gates, confidence, and smoothing: redistribution engine, Hypothesis property tests, confidence caps, EMA, publication-track threshold, and direction.
5. Daily score job: idempotent delete-then-insert per day, `score_runs`, `component_trace`, fixture e2e, Makefile and CI wiring.
6. Stability harness: flip-rate, reproducibility, alias agreement, and window-robustness tests, plus `stability_report`.
7. Admin audit API and web page: timeline, gate history, search signal view, and day decomposition whose contributions sum to the actual delta.
8. Docs and workflow: snapshot workflow score step, weekly trends workflow, shadow-log scaffold, runbook notes, and Phase 5 verification sweep.

## Verification

- Synthetic component inputs produce hand-computed raw scores, redistributed weights, confidence, EMA, publication value, and direction.
- Every eligibility gate has a crafted fixture case: alias disagreement excludes S, low volume gates S, short history gates S/P/I as appropriate, relist precision keeps T ineligible, and insufficient band/model counts gate P.
- The repricing guard acknowledges same-seller repricing at most once per 14 days.
- Price divergence behavior halves P after 4 weeks and excludes P after 8 weeks.
- Hypothesis tests assert redistributed weights sum to 100 for scored models, fewer than three eligible components remain unscored, P never exceeds 25, ceilings hold, and overflow order is inventory then breadth.
- Decomposition tests assert per-component day-over-day contributions sum to the actual raw score delta.
- Stability harness produces a fixture decision artifact and can be re-run on real data for the 5.9 calendar gate.
- Fixture e2e runs migrate, seed, snapshot, match, normalize conditions, aggregate, trends fixtures, and daily score. It writes one `score_daily` row per bag with `published=false`, honest gate outcomes, and an unscored reason when fewer than three components are eligible.
- Public `/bags/{slug}` remains unchanged and continues to render "Not yet scored - tracking since [month]".
- CI adds fixture trends and daily score to the pipeline while keeping vocabulary lint green.

## Key Files

New: `pipeline/alembic/versions/006_score_shadow.py`, `pipeline/app/trends/{source,pytrends_source,csv_source,fixtures,stitch,classify}.py`, `pipeline/app/scoring/{components,price_guard,gates,confidence,smoothing,compute,stability}.py`, `pipeline/jobs/{weekly_trends,daily_score,stability_report}.py`, `pipeline/app/api/admin/score.py`, `web/app/admin/(app)/score/page.tsx`, `pipeline/fixtures/trends/*.json`, `pipeline/tests/test_{trends,score_components,score_gates,score_compute,score_stability}.py`, and `docs/decisions/shadow-log.md`.

Changed: `pipeline/app/contract.py`, score and market model exports, `pipeline/pyproject.toml`, `uv.lock`, `Makefile`, `.github/workflows/{ci,snapshot}.yml`, new `.github/workflows/trends.yml`, `web/lib/{adminApi,adminVocabulary}.ts`, `web/app/admin/(app)/layout.tsx`, and scoring/admin docs.

## Accepted Risks

- pytrends can break or rate-limit without notice; it is optional and isolated behind a source interface with CSV and fixture fallbacks.
- Provisional ladders are intentionally not final. Shadow mode exists to tune thresholds before publication.
- Turnover starts ineligible, so early shadow scores rely on the other components and exercise redistribution daily.
- Search stability gates need repeated same-window pulls, so fixture confidence can be validated before real-data reproducibility is mature.
- Price momentum reconstruction can only use stored listing events and current metadata; this is better than aggregate medians but still depends on event completeness before raw expiry.
- Public score output remains disabled even when internal rows compute successfully.
