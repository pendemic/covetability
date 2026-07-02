# Covetability Score v0 Specification

**Status:** Draft for adoption · July 2026
**Depends on:** `data-contract.md` (definitions and display rules are binding here)

---

## 1. Conceptual identity

> **The Covetability Score v0 measures observable momentum in attention, availability, and active-market pricing for a handbag model.**

It is an *activity index*, not a valuation. It does not measure authenticity, investment quality, confirmed resale value, likelihood of profit, fashion quality, or personal desirability. This sentence (and the exclusion list) appears verbatim in the public methodology page.

Scope: **model level only** (e.g., "Chloé Paddington"). Variants inherit the model score with the label "model-level score." Range 0–100. Classifications: 0–24 Dormant · 25–39 Cooling · 40–54 Stable · 55–69 Building · 70–84 Trending · 85–100 Surging.

**v1 (transaction-anchored) is a separate future generation**: when a repeatable sold-price source exists, sold-price momentum replaces part of the asking-price component. Nothing in v0 may be written as if sold data exists.

---

## 2. Components and base weights

| # | Component | Base weight | Ceiling after redistribution | Signal side |
|---|---|---|---|---|
| S | Search momentum (model-level, bucketed) | 25% | 30% (only after passing the stability gate, §6) | demand-ish |
| I | Active-inventory momentum | 25% | 35% | seller |
| P | Condition-adjusted asking-price momentum | 20% | 25% (hard cap — circularity guard) | seller |
| B | Marketplace breadth | 15% | 25% | mixed |
| T | Listing-turnover proxy (**experimental**) | 15% | 20% | proxy |

The score is majority seller-side by construction. This is acceptable in v0 **only because** the data contract's explanation rules prevent activity from being described as value.

---

## 3. Component definitions

**S — Search momentum.** Weekly Google Trends pulls per model query set (canonical term + top aliases), rescaled against a fixed anchor term, overlapping windows stitched. Signal = 8-week smoothed slope, classified into buckets: strong up (+2) / up (+1) / flat (0) / down (−1) / strong down (−2). Bucket thresholds set during shadow mode. Component score = bucket mapped to 0–100 (strong up=100, up=75, flat=50, down=25, strong down=0). Only the derived classification is stored or displayed.

**I — Active-inventory momentum.** 90-day trend of active matched-listing count (all condition bands, model level), 7-day rolling smoothing. *Declining* inventory scores high (scarcity pressure), rising inventory scores low, normalized against the model's own trailing 6-month volatility once available (fixed percentile ladder until then).

**P — Asking-price momentum.** 30- and 90-day slopes of the condition-mix-adjusted asking median (each band's median moves are computed within-band, then combined by fixed weights so a mix shift toward Excellent listings doesn't read as a price rise). Circularity guards, all mandatory:
- Winsorize listing prices at 2nd/98th percentile before medians.
- Minimum 8 active matched listings model-wide, minimum 5 in a band for that band to contribute.
- Per-listing repricing by the same seller contributes at most once per 14 days.
- Component contribution hard-capped at 25 points even after redistribution.
- Divergence check: if price momentum is strongly positive while S and I are both flat/negative for 4+ consecutive weeks, P is flagged "seller-led repricing" — component halved and the explanation must say asking prices rose without matching interest.

**T — Listing-turnover proxy.** Ended-not-relisted rate (data contract §1.3) vs. its own trailing 90-day average. Labeled *experimental*: internal dashboards show it distinctly; it is first in line for exclusion (§4).

**B — Marketplace breadth.** Count of distinct sources with ≥ 1 valid observation in trailing 30 days (API sources + manual comps with provenance + affiliate feeds). Log-scaled: 1 source = 20, 2 = 45, 3 = 65, 4 = 80, 5+ = 100.

---

## 4. Eligibility gates and redistribution

The score never forces an unreliable component into the sum.

```text
base weights
   ↓
eligibility check per component
   ↓
exclude ineligible components
   ↓
redistribute freed weight pro-rata among eligible components,
   respecting each component's ceiling (§2); weight that cannot
   be placed within ceilings goes to I first, then B.
   ↓
apply confidence penalty (§5) for each excluded component
```

### 4.1 Gates per component

| Component | Ineligible when |
|---|---|
| S | Fails any of: series length < 16 weeks; Trends reports sub-threshold volume for the query set; top-2 alias queries disagree in direction for the current window; repeated same-week pulls differ by more than one bucket; stability gate (§6) not yet passed at launch |
| I | < 8 active matched listings model-wide, or < 45 days of snapshot history |
| P | Minimum listing counts not met; or > 40% of matched listings lack usable condition; or divergence flag active 8+ consecutive weeks (then excluded, not halved) |
| T | Relist-detection precision ≤ 90% on gold set; or < 15 lifecycle events in window |
| B | Never gated (it degrades gracefully by construction) |

### 4.2 UI behavior for exclusions

Excluded components are **shown greyed-out with a reason** ("Insufficient stable search data"), never hidden. If fewer than 3 components are eligible, the model is **not scored**: display "Not yet scored — tracking since [month]."

---

## 5. Confidence

`confidence_raw ∈ [0,1]` = weighted function of: matched-listing count (30%), history length (25%), average match confidence (20%), number of eligible components (15%), source count (10%).

Caps (applied after the function, lowest wins):
- < 90 days of history → cap 0.60
- Any component excluded → cap 0.75; two or more excluded → cap 0.55
- Model-wide matched listings < 15 → cap 0.50
- (Future v1 rule reserved: sold n < 10/90d → cap 0.50)

Display mapping: < 0.40 Low · 0.40–0.70 Moderate · > 0.70 High. Numeric value internal-only in v0.

---

## 6. Search-signal stability gate (operational definition)

Search momentum launches at 25% and may rise to 30% only after passing ALL of the following over a ≥ 60-day pre-launch observation window on the five pilot bags:

1. **Per-bag stability:** for at least 4 of 5 bags, the bucket classification changes in **fewer than 25% of observed weekly transitions**, excluding transitions where the underlying 8-week slope also changed by more than 1.5× its trailing standard deviation (a real move is allowed to flip the bucket).
2. **Pull reproducibility:** repeated pulls of the same window differ by ≤ 1 bucket in ≥ 90% of trials (≥ 20 trials per bag).
3. **Alias agreement:** canonical query and top alias agree in direction in ≥ 75% of weeks per bag.
4. **Window robustness:** 4-week and 8-week slopes agree in sign in ≥ 70% of weeks per bag.

Failure handling: fail (2) or (3) → S stays eligible at 25% but is flagged; fail (1) on 2+ bags → S demoted to 15%; fail (1) on 3+ bags → S excluded until re-tested. Re-test quarterly. The goal is not zero direction changes — a trend signal must change when behavior changes — the goal is that changes not be dominated by sampling noise.

---

## 7. Normalization and change thresholds

- Each component maps to 0–100 before weighting; total score = Σ(weight × component) rounded to integer.
- **Smoothing:** published score is a 7-day EMA of the daily internal score.
- **Change threshold:** the public score updates only when the smoothed value moves ≥ 2 points from the last published value (prevents daily ±1 flutter). Direction arrows (rising/falling/stable) derive from the 30-day published-score slope.
- **Newly matched listings guard:** if a matching-rule change (alias added, exclusion tuned) shifts a model's matched set by > 15%, aggregates are recomputed historically and the score is re-baselined with an internal annotation — a matcher change must never appear as a market event.

---

## 8. Shadow mode and publication criteria

The score runs privately for **a minimum of 30 days, target 60** before any public display. During shadow mode the team must be able to explain every material movement (≥ 3 smoothed points) via the component log. Publication requires:

1. Every material movement in the trailing 30 days has a written explanation traceable to component inputs.
2. No unexplained jumps from: thin-data volatility, search instability, seller repricing feedback, false scarcity (relist misses), condition-mix shifts, or newly matched listings.
3. Match precision ≥ 95% (model-level) on the gold set.
4. Data-contract display rules implemented (confidence + tracking-since always shown; greyed-out exclusions working).
5. Stability gate (§6) has produced a decision on S's weight.

Optional and acceptable: launch the bag pages with component panels visible but **without a single composite number** for the first 30–60 public days, publishing the composite only once shadow-mode criteria hold in production.

---

## 9. Backtesting note (v0-honest)

With no sold data there is no return-based backtest. The v0 validation standard is *explainability and stability*, not predictive accuracy. When sold data arrives (v1), backtest search-bucket transitions and score changes against subsequent realized-price movement; until then, make no predictive claims anywhere in the product.
