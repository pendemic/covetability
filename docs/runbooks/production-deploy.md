# Production Deploy Runbook

Phase 7 can be built on fixtures, but public launch waits on the data-quality gates in
`docs/development-plan.md`: 90 days of real aggregates, current matcher and condition
accuracy checks, and the Phase 5 shadow calendar.

## Required Services

- Hosted Postgres: Neon or Supabase, Postgres 16.
- Pipeline API: Railway or Fly.
- Web: Vercel.
- Scheduled jobs: GitHub Actions using production `DATABASE_URL`.

## Secrets

- `DATABASE_URL`
- `ADMIN_SECRET`
- `EBAY_APP_ID`, `EBAY_CERT_ID`, `EBAY_DEV_ID`
- `EBAY_SOURCE=live`
- `TRENDS_SOURCE=pytrends` or `csv`
- `EPN_CAMPAIGN_ID` when partner tracking is active
- `NEXT_PUBLIC_SITE_URL`
- `NEXT_PUBLIC_ANALYTICS_DOMAIN` and `NEXT_PUBLIC_ANALYTICS_SRC` when analytics is active

## Deployment Steps

1. Create the hosted Postgres database and set `DATABASE_URL`.
2. From a clean checkout, run `make migrate` and `make seed` against production.
3. Deploy the pipeline API with the production environment variables.
4. Verify `GET /health`, `GET /bags`, and `GET /discover`.
5. Deploy the web app with `PIPELINE_API_URL` pointing at the production API.
6. Confirm `/`, `/discover`, `/methodology`, `/affiliate-disclosure`, `/privacy`, and one bag page render.
7. Enable scheduled workflows only after eBay production access is ready.
8. Run one supervised production job chain:
   `snapshot -> match -> normalize-conditions -> aggregate -> trends -> score`.
9. Confirm `score_daily.published` remains false.

## Launch Gate

Do not treat deployment as launch. Public promotion waits until the documented data-quality
gate passes on production data.
