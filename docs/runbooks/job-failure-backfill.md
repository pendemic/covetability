# Job Failure And Backfill Runbook

A missed pipeline day is a data-integrity event. The durable data path is daily
snapshot, matching, condition normalization, aggregates, trends, and score shadow output.

## Detection

Check the latest production rows:

- `snapshot_runs` has a successful row for the expected date.
- `aggregate_runs` has a `daily` row for the same date.
- `score_runs` has a row for the same date.
- Weekly `trend_pulls` and `search_signal_weekly` are current when the trends job is due.

## Backfill

1. Identify the first missing date.
2. Run the snapshot job for the missing date when raw marketplace access still permits it.
3. Run `make rematch` if matcher inputs changed; otherwise run the normal incremental match.
4. Run `make normalize-conditions`.
5. Run `make recompute SINCE=<missing-date> NOTE=job-backfill`.
6. Run `make trends` when the missing window includes a trends pull.
7. Run `make score` for the affected dates.
8. Verify `/discover`, `/bags/<slug>/market`, and the admin score audit page show dated output.

## Escalation

If raw rows have expired past the retention horizon, do not reconstruct asking data from
manual evidence. Leave the durable historical rows unchanged and annotate the incident in
the operator log.
