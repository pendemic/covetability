# eBay Access Tracking

**Status:** Pending as of July 2, 2026.

## Keyset Request Checklist

- Production keyset requested for eBay Browse API.
- Browse API scope included for active listing search and item detail reads.
- OAuth client-credentials flow planned for server-side ingestion only.
- EPN application tracked separately from API access, per ADR-001 and ADR-007.
- No Phase 0 or Phase 1 fixture work depends on granted access.

## Notes

Live Browse API smoke testing starts at Phase 1.6 after credentials are granted. Until then,
ingestion work uses fixture replay and the Phase 0 catalog seed.

## Live Smoke Runbook

Run this only after production Browse API credentials are granted.

1. Add `EBAY_APP_ID` and `EBAY_CERT_ID` locally.
2. Run `EBAY_SOURCE=live EBAY_RECORD_DIR=fixtures/recorded make snapshot`.
3. Verify the Paddington query volume is in the expected 200-600 raw-candidate range.
4. Confirm category `169291` is still the correct women's handbag category and rate-limit headroom is acceptable.
5. Provision hosted Postgres, then run migrations and `python -m seeds.catalog`.
6. Add GitHub secrets `SNAPSHOT_DATABASE_URL`, `EBAY_APP_ID`, `EBAY_CERT_ID`, and `ADMIN_SECRET`.
7. Set repository variable `EBAY_LIVE_ENABLED=true`.
8. Watch the first scheduled `Snapshot` workflow and convert recorded responses into durable fixtures.
