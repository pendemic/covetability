# Architecture Decision Records

## ADR-001 — Active-market product; no sold-data dependency (July 2026)

**Decision:** Covetability v1 is built entirely on data we can collect consistently: eBay Browse API active listings, model-level Google Trends, manual comps with provenance, auction records as context. eBay Marketplace Insights is **not** a dependency — its docs state it is restricted and closed to new users. Sold-anchored scoring is a labeled future generation (Score v1), not a fallback-patched v0.
**Consequence:** All price language is "typical asking"; the score is an activity index (see `covetability-score-v0.md` §1); verdict chips compare against typical asking, upgraded and announced if/when a repeatable sold source exists.

## ADR-002 — Five-bag pilot before catalog expansion (July 2026)

**Decision:** Pilot with Paddington, City, Baguette, Saddle, Pochette Accessoires (rationale in `canonical-catalog.md`). Expansion to ~30 bags requires: ≥95% model-level match precision on the gold set, condition accuracy ≥85% (adjacent-band confusions = half errors), relist detection >90% before lifecycle stats go public.

## ADR-003 — Derived daily aggregates are the durable asset (July 2026)

**Decision:** The permanent dataset is the daily per-(bag × condition-band) aggregate table (`data-contract.md` §5), computed at ingestion time from day one. Raw marketplace rows live in a ~90-day rolling window per API license terms and are never load-bearing. Counsel review of eBay API retention terms before any change to this posture.

## ADR-004 — Gated score components, not fixed weights (July 2026)

**Decision:** Score components pass eligibility gates or are excluded, with capped redistribution and confidence penalties; excluded components display greyed-out with reasons. Base weights 25/25/20/15/15 (search/inventory/price/breadth/turnover); search may earn 30% only via the operational stability gate (`covetability-score-v0.md` §6). Social/editorial signals: 0% weight, human-curated context only.

## ADR-005 — Data contract governs vocabulary (July 2026)

**Decision:** `data-contract.md` is binding on UI copy, schema, and scoring. Prohibited vocabulary list (§6) enforced in review: no "market value," "sell-through," "sold," bare "authenticated," or predictive claims in v0. Two branded terms only: Covetability Score, Covet List.

## ADR-006 — Build the bag page early; publish the score late (July 2026)

**Decision:** The bag intelligence page is prototyped against sample + early real data to validate the data model (insufficient-data states included). The composite score runs in shadow mode ≥30 days (target 60) and is published only when every material movement is explainable (`covetability-score-v0.md` §8). Public launch waits for real history; page development does not.

## ADR-007 — Deferred scope (July 2026)

**Deferred until the intelligence layer is trusted:** Covet List, alerts, saved searches, personalization, public forecasting, reseller opportunity scoring, mobile app, and any automated Poshmark/TheRealReal/Fashionphile collection. Fashionphile/Vestiaire affiliate relationships may be pursued in parallel as partnerships, not scraping.

## ADR-008 - Condition-band enum names (July 2026)

**Decision:** The six public condition bands are encoded exactly as `new_or_unused`, `excellent`, `very_good`, `good`, `fair`, and `poor` in `pipeline/app/contract.py` and the Postgres enum.
**Consequence:** Condition storage, matching fixtures, manual comps, aggregates, and future UI labels share one source of truth. Display copy may format these names for humans, but the stored vocabulary stays stable.
