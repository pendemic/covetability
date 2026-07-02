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
