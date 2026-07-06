# ADR-007 Trigger Review — Covet List Scaffold

Date: 2026-07-06

Phase 8 revisits the smallest honest personalization allowed by ADR-007 after
score publication and the first expansion wave: a per-bag watch called the
Covet List.

Decision:
- Build the data model and public watch API now.
- Key watches by email and bag only.
- Do not add accounts, scraping, alerts, or personalization beyond watched bags.
- Add a digest builder that composes preview payloads from published score rows.
- Do not send email until an email provider and consent flow are explicitly chosen.

Rationale:
The watch model is small, auditable, and tied to published score movements. It
does not alter price ranges, score computation, or the data contract.
