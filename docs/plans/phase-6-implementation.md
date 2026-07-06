# Phase 6 - Manual comps, auction anchors, cultural notes

## Context

Phases 0-5 are committed: schema through migration 006, contract-as-code, fixture-first ingestion, matching, condition normalization, daily aggregates, the public bag page, the admin catalog editor, and the full Score v0 shadow-mode engine (search signal, five components, gates, confidence, smoothing, stability harness, audit screen). Phase 6 builds the **human-operated evidence channels** so breadth (B) has real distinct sources and the bag page gains its high-end context anchor and editorial layer - all with full provenance, and all without contaminating the single-source asking data that is the moat.

Two facts from the current code shape this phase:

- `manual_comps` already exists (migration 001) with CHECK constraints requiring non-empty `source`, non-null `observed_at`, and non-null `condition_band` - the data-contract §4 validity rules are **already enforced at the DB layer**. Phase 6 adds the admin write path, one more constraint (`entered_by` + `sold_confirmed` consistency), and the public/scoring wiring.
- `daily_aggregates` and the listing verdict are computed **only** from `listings_raw` (`aggregates/compute.py`, `api/public/listings.py`). So "auction records never enter aggregates or verdict math" is already **structurally** true; Phase 6 must lock it with tests and must NOT introduce a path that breaks it.
- `compute_breadth` (Phase 5) already counts `manual_comps.source`, but it counts **every** `source_type`, including `auction_record`. Per data-contract §4 auction records must never feed a score component. This is a Phase 5 over-count that Phase 6 corrects.

## Decisions

- **Manual comps do not enter `daily_aggregates` or the typical-asking ranges in v0.** They are heterogeneous cross-marketplace observations; blending them into the winsorized p25-p75 medians would break the single-source homogeneity ADR-003 depends on. In v0 valid non-auction manual comps feed **breadth (B)** and **context display only**. Cross-source asking blending is a labeled future decision, not a v0 patch.
- **Auction records (`source_type = auction_record`) are context anchors only.** They are excluded from every `daily_aggregates` row, every score component, and all verdict math (data-contract §4, hard invariant). They surface **only** in a dedicated public section. A test asserts each of these exclusions.
- **Breadth counts `api` + `manual` sources with valid observations in the trailing 30 days; `auction_record` and `user_submitted` are excluded.** This corrects the Phase 5 over-count and keeps B honest (B is a score component; §4 bars auction rows from all components; `user_submitted` has no channel yet per ADR-007).
- **Public section naming avoids the prohibited vocabulary.** Data-contract §4 calls this the "notable sales" context, but §6 prohibits "sales"/"sold" site-wide and `vocab-lint` enforces it over `app/` + `lib/`. The public heading is **"Notable auction results"** and rows read "Realized at auction - [house], [date]" (`price_type = realized` is allowed vocabulary). The `vocab-lint` allowlist is **not** weakened.
- **Cultural-context notes are a 0%-weight editorial layer (ADR-004).** Stored in a new `cultural_notes` table, rendered in "Why it's moving" as clearly-labeled context ("Editorial context - tracked, not scored", per data-contract §3 rule 4), and **excluded from score math by construction**: nothing in `app/scoring/` or `app/trends/` ever imports the cultural-notes or auction models. A guard test asserts this.
- **Provenance is validated at both the form and DB layers** (data-contract §4): `source`, `source_type`, `observed_at`, `condition_band`, `entered_by`, `price_type` required; `sold_confirmed = true` only when `source_type = auction_record`. Pydantic rejects at the API with 422; a DB CHECK backs it so a bad row cannot be written by any path.
- **A new public `/bags/{slug}/context` endpoint** returns notable auction results + editorial context notes (both display-only), fetched alongside market/history/listings by the bag page. This keeps the `/market` response lean and the new concern independently testable.

## Design

Migration 007, `007_evidence_channels.py`, adds the editorial layer and hardens comps. New table `cultural_notes` (`bag_model_id`, `observed_on date`, `note text`, `entered_by`, `created_at`). New `manual_comps` CHECK constraints: `ck_manual_comps_entered_by_required` (non-empty `entered_by`) and `ck_manual_comps_sold_confirmed_auction` (`NOT sold_confirmed OR source_type = 'auction_record'`). New index `ix_manual_comps_bag_type_observed` on (`bag_model_id`, `source_type`, `observed_at`) for the notable-results and breadth queries.

Admin write path lives in `app/api/admin/comps.py`: create/list/delete for manual comps and auction records (one endpoint family, `source_type` selects behavior) and create/list/delete for cultural notes. Pydantic request models mirror the DB constraints so validation fails fast with a field-level 422 before the insert. Registered in `app/api/admin/__init__.py`.

Public read path lives in `app/api/public/context.py`: `GET /bags/{slug}/context` returns `notable_auction_results` (auction-record comps: realized price, house, date, condition band, provenance URL, `sold_confirmed`) and `context_notes` (cultural notes, newest first). Response schemas go in `app/api/public/schemas.py`.

Breadth correction is a one-function change in `app/scoring/components.py`: `compute_breadth` filters `manual_comps.source_type == manual` (via a `BREADTH_SOURCE_TYPES` allowlist in `contract.py`) so auction and user-submitted rows never lift B.

Web: a new admin evidence page `web/app/admin/(app)/evidence/page.tsx` with a keyboard-friendly, provenance-complete entry form (manual comp / auction record / cultural note, toggled by type), wired through `web/lib/adminApi.ts`, `web/lib/adminVocabulary.ts`, and the admin nav. The public bag page gains a "Notable auction results" section (rendered from `/context`) and an "Editorial context" block inside "Why it's moving"; new display components in `web/app/components/MarketComponents.tsx`, fetchers in `web/lib/publicApi.ts`, and strings in `web/lib/vocabulary.ts` (chosen to keep `vocab-lint` green).

`docs/runbooks/manual-evidence-cadence.md` documents the weekly operating cadence: Terapeak reads where the license permits, Vestiaire/Fashionphile asking observations, auction-result entry, and the provenance checklist an operator must satisfy per row.

## Build order

1. **Schema + constraints.** Migration 007 (`cultural_notes`, the two `manual_comps` CHECKs, the index), `CulturalNote` model + exports, `BREADTH_SOURCE_TYPES` in `contract.py`, migration up/down roundtrip, contract/constraint tests.
2. **Breadth correction.** Filter `compute_breadth` to the source-type allowlist; unit test: a `manual` source moves B 20 -> 45; an `auction_record` source does not move B.
3. **Admin comps/auction API.** `app/api/admin/comps.py` create/list/delete with Pydantic provenance validation; register router. Tests: comp missing condition/source/date/entered_by rejected at the form layer (422) and, via a raw insert, at the DB layer (IntegrityError); `sold_confirmed` on a non-auction row rejected; auction row stored with `source_type=auction_record`.
4. **Public context API + exclusion proofs.** `/bags/{slug}/context` (notable auction results + context notes) and schemas. Tests asserting an auction record and a manual comp appear in `/context` (auction) but in **no** `daily_aggregates` row, **no** `/market` band, and **no** `/listings` verdict.
5. **Cultural notes end-to-end.** Admin CRUD + context wiring; a guard test that greps `app/scoring/` and `app/trends/` and asserts neither imports `CulturalNote` nor reads `manual_comps` with `auction_record`.
6. **Admin evidence web page.** Entry form + list/delete; `adminApi`/`adminVocabulary`/nav wiring; tsc + eslint + vocab-lint green.
7. **Public bag page.** "Notable auction results" section + "Editorial context" block; MarketComponents + publicApi + vocabulary; Lighthouse-safe; vocab-lint green.
8. **Docs + verification sweep.** Cadence runbook; check off dev-plan 6.1-6.4; full local CI-equivalent (ruff, pytest, migrate/seed, e2e pipeline, web tsc/eslint/vocab/build); commit + push.

## Verification

- A manual comp missing condition (or source, date, `entered_by`) is rejected at **both** the form layer (422) and the DB layer (CHECK/IntegrityError).
- An auction record appears in "Notable auction results" and provably **not** in any `daily_aggregates` row, any `/market` band, or any `/listings` verdict; a `sold_confirmed` flag is accepted only with `source_type=auction_record`.
- Adding a second distinct **manual** source moves B from 20 -> 45 on the next scoring run; adding an **auction** source leaves B unchanged.
- Cultural notes render in "Why it's moving" labeled as editorial context; a guard test proves `app/scoring/` and `app/trends/` never touch the auction/cultural evidence.
- `vocab-lint` stays green with the new public section (no "sales"/"sold" leak); `daily_score` and `/market` outputs are unchanged by the presence of auction/cultural rows except for B's source count.
- Full pipeline suite + web tsc/eslint/vocab/build green.

## Key files

New: `pipeline/alembic/versions/007_evidence_channels.py`, `pipeline/app/api/admin/comps.py`, `pipeline/app/api/public/context.py`, `pipeline/app/models/evidence.py` (`CulturalNote`), `pipeline/tests/test_{comps_api,context_api,breadth_sources,evidence_isolation}.py`, `web/app/admin/(app)/evidence/page.tsx`, `docs/runbooks/manual-evidence-cadence.md`.

Changed: `pipeline/app/contract.py` (`BREADTH_SOURCE_TYPES`), `pipeline/app/scoring/components.py` (breadth filter), `pipeline/app/models/{__init__,market}.py`, `pipeline/app/api/admin/__init__.py`, `pipeline/app/api/public/schemas.py`, `web/lib/{adminApi,adminVocabulary,publicApi,vocabulary}.ts`, `web/app/components/MarketComponents.tsx`, `web/app/admin/(app)/layout.tsx`, `web/app/bags/[slug]/page.tsx`, `docs/development-plan.md`.

## Accepted risks

- **Cross-source asking heterogeneity.** Manual comps stay out of the typical-asking aggregates in v0 on purpose; if a later generation blends them, it needs its own source-normalization and a re-baseline, not a silent merge.
- **Breadth gaming.** B rises with distinct sources, so a careless operator could inflate it; mitigation is provenance-required, operator-only entry in v0 and the source-type allowlist. Revisit if B ever dominates a published score.
- **The one legitimate "realized" surface.** Auction results are the only place realized prices appear; they are kept in a physically separate table read path and never join asking data, so the honesty guarantee is structural, not conventional.
- **Manual-entry fatigue.** The weekly cadence is real operator work; the form is keyboard-first and the runbook bounds the scope (a few high-signal comps + one note per bag per week), consistent with the labeling-fatigue mitigation from Phase 2.
- **Auction record availability.** Auction houses publish irregularly; B and the notable-results section degrade gracefully (empty section, B unaffected) when no records exist.
```
