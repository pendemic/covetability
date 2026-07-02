# Covetability Data Contract v1.0

**Status:** Draft for adoption · July 2026
**Purpose:** This document defines every public-facing metric, what it means, what it must never be made to imply, and how the product behaves when data is insufficient. It governs the database schema, analytics, UI copy, and score methodology. Any change to a metric's definition, display language, or minimum data requirement is a change to this contract and requires a decision-record entry.

**Governing principle:** Covetability v1 is an **active-market observation product**. It describes what sellers are asking, how inventory is moving, and how attention is changing. It does not have confirmed transaction data and must never write, imply, or visually suggest that it does.

---

## 1. Public metrics

### 1.1 Typical asking range

| | |
|---|---|
| **Meaning** | The p25–p75 range of asking prices among matched, condition-banded, active listings for a canonical bag over the trailing 14 days. |
| **Does NOT mean** | Confirmed sale value. Market value. What the bag is "worth." |
| **Calculation** | Per (bag_model × condition_band): winsorized asking prices (2nd/98th pct) of active matched listings, trailing 14-day window, item price + shipping where shipping is known (`median_total_price`), item price otherwise (labeled). |
| **Minimum data** | ≥ 5 active matched listings in the band. |
| **Display term** | "Typical asking range — [Condition]". Never "market value," "estimated value," "worth." |
| **Insufficient-data behavior** | Band displays "Insufficient reliable data" — never a widened range, never a value borrowed from an adjacent band. |

### 1.2 Listing price verdict

| | |
|---|---|
| **Meaning** | The percentage difference between one listing's asking price and the typical asking range midpoint for its condition band. |
| **Does NOT mean** | A deal rating, an appraisal, or a prediction that the listing will or should sell at any price. |
| **Calculation** | (listing_total_price − band_median) / band_median, shown only when the band meets its minimum data requirement AND listing match confidence ≥ 0.90 AND condition confidence is not "indeterminate." |
| **Display term** | "≈ 12% above typical asking for Good condition." Never "above market," "overpriced," "fair value." |
| **Insufficient-data behavior** | No verdict chip. Do not show "N/A" — omit the element. |

### 1.3 Inventory exit rate (listing turnover proxy)

| | |
|---|---|
| **Meaning** | The share of matched listings that ended in the window and were not detected as relisted within 14 days. |
| **Does NOT mean** | Sell-through. Confirmed sales. Demand. |
| **Calculation** | ended_not_relisted / (active at window start + new in window), 30-day window. Relist detection: seller_id + normalized title + image perceptual hash; reappearance ≤ 14 days from same seller = relist. |
| **Minimum data** | ≥ 15 lifecycle events in window AND relist-detection precision validated > 90% on the gold set. |
| **Display term** | "Listing turnover" or "listings that ended." The strings "sell-through," "sold," "sales rate" are prohibited for this metric. |
| **Insufficient-data behavior** | Metric hidden entirely; internal dashboards may show it flagged "experimental." |

### 1.4 Search momentum

| | |
|---|---|
| **Meaning** | The direction and rough magnitude of change in search interest for the bag **model** (never variant), classified into buckets (strong up / up / flat / down) from an 8-week smoothed slope of anchor-rescaled Google Trends pulls. |
| **Does NOT mean** | Consumer demand. Purchase intent. Number of searches (we never display absolute or index values — derived classification only; Google's data is not redistributed). |
| **Minimum data** | Passes the eligibility gate in the Score v0 spec (§4.2). |
| **Display term** | "Search interest: rising / steady / declining." |
| **Insufficient-data behavior** | "Insufficient stable search data" — shown, not hidden, so the absence is honest. |

### 1.5 Covetability Score

| | |
|---|---|
| **Meaning** | **An index of observable momentum in attention, availability, and active-market pricing for a handbag model.** Full definition, components, and gates: `covetability-score-v0.md`. |
| **Does NOT mean** | Authenticity. Investment quality. Confirmed resale value. Likelihood of profit. Fashion quality. Personal desirability. A price prediction. |
| **Granularity** | Model level only. Variants display the model score labeled "model-level score"; variants never receive their own score in v0. |
| **Display term** | "Covetability Score: 78 — Trending · Confidence: Moderate · Tracking since July 2026." Always shown with confidence and tracking-since date. Never shown without its classification word. |
| **Insufficient-data behavior** | If the score cannot be computed under the v0 spec, display "Not yet scored — tracking since [month]" rather than a provisional number. |

### 1.6 Confidence

| | |
|---|---|
| **Meaning** | How much reliable data supports the score and price ranges: listing counts, history length, match confidence, component eligibility. |
| **Does NOT mean** | Probability the score is "correct." Statistical confidence interval. |
| **Display term** | Low / Moderate / High plus a one-line reason ("based on 43 matched listings over 4 months"). Numeric confidence stays internal in v0. |

---

## 2. Authentication label taxonomy

The bare word "Authenticated" is prohibited. Every listing shows exactly one of:

| Label | Applies when | Never applies when |
|---|---|---|
| **Platform-authenticated** | The platform itself physically authenticated the item before/at sale (e.g., authenticated-reseller inventory). | The seller merely claims authentication. |
| **Marketplace authentication program** | The listing qualifies for the marketplace's authentication-at-sale program (e.g., eBay Authenticity Guarantee eligibility). | Program eligibility cannot be confirmed from listing data. |
| **Seller claim only** | The seller asserts authenticity (receipts, cards, "guaranteed authentic") with no platform program. | — |
| **Authentication status unknown** | None of the above can be established. | — |

Site-wide disclosure, verbatim: **"Covetability does not authenticate items. Labels describe marketplace programs and seller claims only."**

---

## 3. Score-explanation rules ("Why it's moving")

Explanations are generated from measured inputs only, and must obey:

1. Every sentence maps to a specific stored metric and window ("Search interest rose over the past 30 days" ⇐ search bucket transition).
2. **Activity, not value:** "Asking prices increased 11%" is legal; "the bag is worth 11% more," "gaining value," "appreciating" are prohibited.
3. Never explain with a signal whose component was gated out of the score that day.
4. Ineligible/absent components are named as absent ("social signals are tracked editorially, not scored"), not silently omitted.
5. 3–5 observations maximum, ordered by contribution magnitude.
6. AI may rephrase metric facts into prose; it may never introduce a fact not present in the metric record.

---

## 4. Source provenance requirements

Every observation stores: `source`, `source_type` (api / manual / user_submitted / auction_record), `observed_at`, `entered_by` (for manual), `listing_url` (where permitted), `sold_confirmed` (boolean; true ONLY for auction records and any future transaction feed), `price_type` (asking / realized), `shipping_included`, `match_confidence`, `condition_raw`, `condition_band`, `condition_confidence`.

Rules:
- **Manual comps are evidence with provenance**, not numbers typed into a field. A manual comp missing source, date, or condition is invalid and excluded from aggregates.
- **Auction-house records** (`source_type: auction_record`) are context anchors for the high end. They are displayed in a separate "notable sales" context and **never blended into typical asking ranges or score components.**
- Raw marketplace listing rows expire per API license terms (default 90-day rolling window). **Derived daily aggregates are first-class permanent records** and the durable dataset.
- Rebag Clair or similar third-party indices: internal calibration only; never displayed, never scored.

---

## 5. Daily aggregate record (the durable asset)

One row per (bag_model × variant-nullable × condition_band × day):

```text
bag_model_id, variant_id (nullable), condition_band, observation_date,
active_listing_count, new_listing_count, ended_listing_count, possible_relist_count,
median_asking_price, p25_asking_price, p75_asking_price, median_total_price,
source_count, matched_listing_count, average_match_confidence
```

This table is computed in the same job as ingestion, from day one, before public launch. It is the moat.

---

## 6. Prohibited vocabulary (site-wide)

| Prohibited | Required instead |
|---|---|
| market value, worth, valuation | typical asking range |
| sold, sell-through, sales | listings that ended, listing turnover |
| authenticated (bare) | one of the four taxonomy labels |
| demand (from search data) | search interest |
| investment, appreciating, ROI | (no substitute — do not make the claim) |
| forecast, prediction (v0) | momentum, direction |
