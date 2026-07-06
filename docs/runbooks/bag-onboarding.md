# Bag Onboarding Playbook

Use this recipe for each expansion wave. The pilot remains the quality bar:
catalog entry, fixture/live candidates, measured matching precision, condition
accuracy, aggregate history, score shadow review, then publication.

## Per-Bag Steps

1. Add the catalog identity.
   - Preferred durable path: add a `CATALOG` entry in `pipeline/seeds/catalog.py`.
   - Admin path: create the bag in Catalog, then add aliases, variants, exclusions, and editorial fields.
   - Code-only step: add color-family and model-specific matching terms in `pipeline/app/matching/keywords.py`.
2. Add initial queries and run the catalog-wide pipeline:
   - `make snapshot EBAY_SOURCE=fixtures` during development.
   - `make snapshot EBAY_SOURCE=live` once eBay keys are active.
   - `make rematch`
   - `make normalize-conditions`
   - `make aggregate`
3. Label approximately 150 candidates in the labeling UI.
4. Enforce the current gates:
   - Matcher: precision >= 95%, recall >= 70%, variant attribution >= 85%.
   - Conditions: `make evaluate-conditions`, target >= 85% with adjacent-band half errors.
5. Run at least 2 weeks of daily ingestion before making the page useful; public launch and score publication wait for the 90-day aggregate gate and the Phase 5 shadow-mode calendar.
6. Run trends and score shadow:
   - `make trends`
   - `make score`
   - `make stability`
   - `make apply-stability`
7. Publish only after the Phase 8 readiness checklist passes or an operator records a force-publish reason.

## Expansion Waves

Move in waves of about five models. Suggested next wave: Speedy, Jackie,
Re-Edition, Spy, Stam. Thirty bags is roughly five waves; each wave repeats
the same gates rather than borrowing trust from the pilot.
