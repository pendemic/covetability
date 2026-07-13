# Phase 9 - Design implementation (Bag Profile + design-system rollout)

## Context

The design canvas **"Vintage Designer Bag Intelligence"** (claude.ai/design project `48a1f99c`, file `Bag Profile.dc.html`, imported to `design/imports/`) is the source of truth for the public surface. It contains four turns of screens under the placeholder house name **"Provenance"**:

- **Turn 02 - product page:** `2A` Model overview (aggregate market + every colorway ranked), `2B` Variant detail (one colorway x size, charts + score + listings). **This is the "Bag Profile" the file is named for and the anchor of this phase.**
- **Turn 03 - landing dashboard** (`3A`).
- **Turn 04 - mobile** (`4A`).
- **Turn 05 - web:** `5A` Brand page, `5B` Signals dashboard, `5C` Compare. **Mobile:** `5D` Discover, `5E` Search+filters, `5F` Watchlist, `5G` Product list.

Two facts set the shape of the work:

1. **The visual language is already shipped.** `web/app/globals.css` tokens already match the design 1:1 - `--ink #2b2520`, `--paper #e7decf`, `--surface #fcf9f2`, `--copper #b0623e`, `--line #e0d4bf`, and the Cormorant Garamond / IBM Plex Mono / Hanken Grotesk stack via `--font-serif/mono/sans`. **Phase 9 is layout + data wiring + honest-vocabulary translation, not a restyle.** No new color/type system.
2. **The design is aspirational and violates settled v1 direction in named places.** It shows a published per-variant "Trend score", a `Sell-through %` card, a `Days on market` card, a `Forecast - 3-6 months` panel, and "search leads price -> precursor to a median step-up". Against `web/lib/vocabulary.ts::prohibitedVocabulary` (`sold`, `sell-through`, `sales`, `forecast`, `prediction`, `demand`, `investment`, `worth`, `market value`) and the v1 decisions in `memory/covetability-v1-direction.md` (scores **model-level only**, honest active-market, forecasting **deferred**), several design elements must be **translated, relabeled, or dropped**, never copied verbatim. This reconciliation is the intellectual core of the phase, not a cleanup pass.

The current bag page (`web/app/bags/[slug]/page.tsx`) already renders a strong single-model page (band ranges, model score ring, observations, listings, auction records, history charts, variant panels, Covet List). Phase 9 restructures it to the 2A/2B information architecture and then extends the design across the rest of the surface. Everything is fixture-renderable now; nothing here is gated on eBay keys.

## Decisions

### D1 - Vocabulary translation table (binding; enforced by `vocab-lint`)

Every design string maps through this table before it ships. The design word is on the left; what we render is on the right.

| Design (Provenance) | Ships as | Why |
| --- | --- | --- |
| "Trend score" / "Model trend score" / "House trend score" | **Covetability Score** | Only two branded terms exist (`covetList`, `score`); `metricDisplayVocabulary.score`. |
| "Sell-through 58%" (2B card) | **Listing turnover** (`listingTurnover`) | `sell-through` is prohibited; contract mandates "listing turnover" / "listings that ended". |
| "Days on market" (2B card) | **Listing turnover** proxy, or drop the card | "days on market" reads as a sold-velocity claim; keep to the turnover proxy language. |
| "Listing-demand imbalance" (5B signal) | **Listing-turnover proxy** | `demand` is prohibited. |
| "Forecast - 3-6 months / Likely to increase" (5B) | **Removed** in v1; replaced by an **observation** panel ("Why it's moving") that only describes what already happened | `forecast`/`prediction` prohibited; forecasting deferred (memory). |
| "Search leads price -> precursor to a median step-up" | **Removed** predictive claim; the two-series chart stays but captioned descriptively (no lead/precursor language) | Same. |
| "Social-mention momentum (Pinterest/TikTok)", "Editorial momentum" as **score inputs** with weights 25/20/20/15/10/10 | Score components stay the **v0 set** (search 30 / active-inventory 25 / asking-price 20 / listing-turnover 15 / breadth 10) from `docs/product/covetability-score-v0.md`; social/editorial may appear as **context**, never as score weights | The published score is v0; the 5B "signals" screen must render the *real* component set from `market.score.components`, not the mockup's. |
| "▲ across 9 sites" | **Marketplace breadth** ("N marketplaces") | Neutral, matches breadth component. |

The score identity/exclusions copy (`scoreIdentityStatement`, `scoreExclusions`) must be reachable from every screen that shows the score.

### D2 - Scores are model-level only (no per-variant Covetability Score)

The 2A variants table and 2B variant cards show a per-colorway score in the mockup. v1 forbids this ("scores at model level only"). **Ship:** the variants/colorway table shows **median asking + listing-turnover proxy + a search-interest sparkline** per colorway, and a single **model-level Covetability Score** at the top. The per-row "score/dir" column is replaced by the sparkline + a neutral momentum chip (from `observations`), not a number out of 100. `market.score` has no per-variant field and none is added.

### D3 - Size-as-product is modeled as separate bags, not a new schema level

The design's hierarchy is brand -> model -> **size (product)** -> colorway (variant). The data model is brand -> `bag_model` (slug) -> `variants` (colorways, `is_separate_market`). Rather than add a schema level for 4 pilot bags, **each tracked (model x size) is its own `bag_model` slug** (e.g. `chloe-paddington-medium`), and the 2A "Size" chip row links between sibling slugs. This keeps the pilot's per-(bag x condition-band) aggregate the unit of the moat and avoids a migration. A `sibling_slugs`/`size_group` grouping is a small additive field on `bag_models`, decided in 9.1, only if the chip row needs it. (Colorways remain `variants`; `is_separate_market` still drives the "Separate markets" split already in `MarketResponse.variants`.)

### D4 - Reuse `MarketComponents.tsx`; extend, don't fork

The component inventory (`StatCard`, `BandRangeCard`, `VariantPanel`, `ScoreRing`, `ScoreBreakdown`, `ObservationList`, `ListingsTable`, `HistoryCharts`, `LineChart`, `AuctionRecordsTable`, `ContextNotes`, `Chip/Badge/Tag`) already covers most 2A/2B primitives. New primitives are small and additive: `Sparkline` (row-level SVG path, the design's `vector-effect="non-scaling-stroke"` pattern), `ColorwayBars` (median-by-colorway horizontal bars), `SizeChips`, `VariantTable`, `VolumeBars`. No component is rewritten; the page is recomposed around them.

### D5 - Score renders honestly whether published or not

Per the Phase 7/8 posture, every screen must read correctly with the score in `not_yet_scored` state. The 5B "Signals" screen and the 2A/2B score ring both branch on `market.score.status` exactly as the current page does (`ScoreRing` + `ScoreBreakdown` vs component placeholders).

## Design (per-screen mapping: design element -> real data -> component)

### 9.1 Bag Profile - product page (2A model overview + 2B variant detail)

The two are one route with a selected-colorway state, not two pages. Server component loads via the existing `loadBagPage` fan-out (`getBag`, `getMarket`, `getHistory`, `getListings`, `getAuctionRecords`, `getContextNotes`); colorway selection is a client sub-tree.

**2A aggregate header**
- Breadcrumb `Discover > Brand > Model` + `Product` tag -> `bag.brand.name`, `bag.model_name`.
- Size chips -> sibling slugs (D3); links, current size marked.
- 4 stat cards -> `StatCard`:
  - "Median - all colorways" -> aggregate typical asking from `market.bands` (label **Typical asking**, `median_asking_price` + `p25`/`p75` range).
  - "Active listings" -> `market.totals.active_matched_listing_count` (caption: breadth = "N marketplaces").
  - "Model trend score" -> **Covetability Score** via `ScoreRing`/value (D1); dir chip from `scoreClassificationLabels`.
  - "Colorways" -> `market.variants.length`.
- Variants table -> new `VariantTable`: per colorway row = swatch + name + `median_asking_price` + `Sparkline` (search-interest series from `getHistory` variant series) + neutral momentum chip (**no score**, D2). Row click selects the colorway (drives 2B section).
- Search-interest chart (model) -> `LineChart` over `history.activity` / observations; honors `insufficient_stable_search_data`.
- Median-by-colorway bars -> new `ColorwayBars` from `market.variants[].bands` medians.
- "Top mover" blurb -> `ObservationList`-derived sentence (reuse observation sentences; no predictive phrasing).

**2B variant detail (selected colorway)**
- Title + variant switcher chips -> `market.variants`; back-link to model.
- 4 stat cards -> `StatCard`: **Median asking** (variant band), **Active listings** (variant), **Listing turnover** (D1, replaces "days on market"), **Listing turnover proxy** (D1, replaces "Sell-through"). Only render cards whose band has `status: "ok"`; otherwise `insufficientReliableData`.
- 3 charts -> `HistoryCharts` variant series: median asking price (`LineChart`), search-interest index (`LineChart`), active-listing volume (`VolumeBars`, new).
- Score ring + confidence + momentum list + "Why it's moving" -> `ScoreRing`/`ScoreBreakdown` (**model-level**, labeled as such) + `ObservationList`. The momentum list = search-interest / asking-price / listing-volume observation deltas. "Why it's moving" = observation prose (descriptive only).
- Listings -> `ListingsTable` (already includes auth disclosure, EPN wrapping, item location + seller attribution).

### 9.2 Brand page (5A)

New route `web/app/brands/[slug]/page.tsx`. Needs a public endpoint `GET /brands/{slug}` returning house rollup + model list. Header stats: **House Covetability rollup** (aggregate, honestly labeled - or omit if no model-level rollup is defined; do not invent a "house score" the scoring engine doesn't produce), models tracked, active listings, breadth. Models table = `VariantTable` shape reused, rows link to each model's Bag Profile. "House interest" chart from aggregated history. **No forecast.** "Cooling" label allowed (it's in `scoreClassificationLabels`).

### 9.3 Signals screen (5B) - the honest version

New route `web/app/bags/[slug]/signals/page.tsx` (or a section on the Bag Profile). This screen exists to make the score **transparent**, which aligns with v1 - but it must render the **real component set** from `market.score.components` with their real weights/values/contributions (already in `ScoreBreakdown`), not the mockup's social/editorial weights. Score ring, per-component weight/normalized/points table, momentum windows (7/30/90/365-day observation deltas). **Delete the "Forecast" card and the "search leads price" predictive caption** (D1). Renders placeholders when `status !== "published"` (D5).

### 9.4 Compare (5C)

New route `web/app/compare/page.tsx`, client-stateful pool of 2-4 bags. Metric rows map to real fields: median asking, **Covetability Score** (model-level), price 90d delta, search 30d delta, active listings, **listing turnover** (not sell-through/days-on-market), confidence, era/material. Needs a batch endpoint `GET /compare?slugs=a,b,c` or N parallel `getMarket` calls. Drop any prohibited row.

### 9.5 Discover / landing (3A) reconciliation

The current `/discover` has three modules (`featured`, `rising_asking_interest`, `under_the_radar`). The design (`buildDiscover`) adds **Fastest rising**, **Rising price**, **Emerging (first tracked)**, **Cooling/Losing**, **Under the radar**. Extend `DiscoverResponse.modules` additively (new module keys) so the richer layout renders; "Cooling" is allowed, "Losing" -> "Cooling". Keep every module honest under insufficient-data.

### 9.6 Mobile screens (5D-5G, 4A)

Responsive collapse of the above, not separate routes. The design's mobile frames (Discover, Search+filters, Watchlist, Product list) are the < 640px layouts of 9.5 / catalog-search / Covet List / 9.1. "Watchlist" == **Covet List** (`covetList`). Deliver as CSS breakpoints + a mobile bottom-nav, no duplicate pages.

## Build order

1. **9.1 Bag Profile (anchor).** New primitives (`Sparkline`, `ColorwayBars`, `VariantTable`, `VolumeBars`, `SizeChips`) in `MarketComponents.tsx`; recompose `bags/[slug]/page.tsx` into the 2A aggregate + 2B selected-colorway IA; wire colorway selection as a client sub-tree; apply the D1 translation table and D2 model-level-score rule. Size-chip sibling linking (D3) - additive `bag_models` grouping field + seed only if needed. Fixture-render all 5 pilot bags. Tests: page renders with score published **and** not-yet-scored; no prohibited string; per-variant score absent.
2. **9.3 Signals screen.** Reuse `ScoreBreakdown`; add momentum-windows + component table; **delete forecast/lead claims**; placeholder path. Test: renders the real component set, no `forecast`/`prediction`/`sell-through` in output, honest when unpublished.
3. **9.5 Discover reconciliation.** Extend `discover.py` + `DiscoverResponse` with the additional modules; update `web/app/discover/page.tsx`; "Cooling" module. Tests assert modules compute from aggregates with no composite-score dependency and honor insufficient-data.
4. **9.2 Brand page.** `GET /brands/{slug}` + `web/app/brands/[slug]/page.tsx`; house rollup labeled honestly (or omitted); models table links to Bag Profiles.
5. **9.4 Compare.** Batch endpoint or parallel fetch; `web/app/compare/page.tsx`; real metric rows only.
6. **9.6 Mobile + nav.** Responsive breakpoints across 9.1-9.5; mobile bottom-nav; "Watchlist" surfaced as Covet List. Manual/E2E at 402px and desktop widths.
7. **Vocab + verification sweep.** `vocab-lint` over every new/changed screen (must catch the translation table); check off the dev-plan; full web `tsc`/`eslint`/build; pipeline tests for new endpoints; commit.

Build 9.1 first and completely - it is the named deliverable and it exercises every new primitive the later screens reuse.

## Verification

- **9.1**: all 5 pilot Bag Profiles render from fixtures at desktop + mobile; colorway selection updates 2B without a full navigation; the 4 aggregate cards and 4 variant cards degrade to `insufficientReliableData` when a band lacks data; **no per-variant number-out-of-100 anywhere**; model-level Covetability Score present once.
- **Vocabulary**: `vocab-lint` green across all Phase 9 screens; grep for `sell-through`, `sold`, `forecast`, `prediction`, `demand`, `days on market`, "trend score" returns nothing in rendered output; the design's forecast panel is absent.
- **Score honesty**: every score surface renders correctly for both `market.score.status` values; the 5B component table matches `market.score.components` (v0 set + weights), not the mockup's.
- **Discover/Brand/Compare**: compute entirely from `daily_aggregates` (+ editorial); thin bags render insufficient-data, never borrowed values; Compare/Brand show no prohibited row.
- **Regression**: existing bag-page E2E, `tsc`, `eslint`, pipeline pytest all green; EPN wrapping + item-location/seller attribution still present on listings.

## Key files

New: `web/app/brands/[slug]/page.tsx`, `web/app/compare/page.tsx`, `web/app/bags/[slug]/signals/page.tsx` (or section), `pipeline/app/api/public/brands.py`, `pipeline/app/api/public/compare.py`, `pipeline/tests/test_phase9_design.py`, `design/imports/Bag Profile.dc.html` (reference, saved).

Changed: `web/app/bags/[slug]/page.tsx` (2A/2B recompose), `web/app/components/MarketComponents.tsx` (`Sparkline`, `ColorwayBars`, `VariantTable`, `VolumeBars`, `SizeChips`), `web/app/discover/page.tsx` + `pipeline/app/api/public/discover.py` (+ `DiscoverResponse` modules), `web/lib/publicApi.ts` (brand/compare types + module keys), `web/lib/vocabulary.ts` (any new labels), `web/app/globals.css` (layout classes only - no new tokens), `web/app/layout.tsx` (mobile nav), `docs/development-plan.md` (9.x checkboxes). Optional additive migration only if D3 grouping field is needed.

## Accepted risks

- **The design is a maximalist mockup; v1 is deliberately narrower.** The real work is *saying no* to the forecast panel, per-variant scores, and sell-through - honoring `memory/covetability-v1-direction.md` over the pixels. The translation table (D1) and D2 are the guardrails; `vocab-lint` is the backstop.
- **Size-as-product (D3) is modeled by convention, not schema.** Fine for 5-30 pilot bags; if the catalog grows a true size dimension, revisit with a migration. Documented, not hidden.
- **A "house score" (5A) may not exist in the engine.** Do not fabricate one; label the brand rollup honestly or omit the number. Better an empty-but-true header than an invented metric.
- **Launch remains data-gated, not build-gated** (Phase 7 risk still stands): Phase 9 is fully fixture-renderable now, but real history + matcher/condition gates still gate going public.
