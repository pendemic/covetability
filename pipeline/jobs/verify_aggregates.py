from __future__ import annotations

from sqlalchemy import func, select

from app.contract import MIN_LISTINGS_PER_BAND
from app.db import SessionLocal
from app.models import AggregateRun, BagModel, DailyAggregate


def main() -> int:
    with SessionLocal() as session:
        latest_date = session.scalar(select(func.max(DailyAggregate.observation_date)))
        if latest_date is None:
            raise SystemExit("Expected aggregate rows, found none.")

        bag_count = session.scalar(select(func.count()).select_from(BagModel))
        bags_with_rows = session.scalar(
            select(func.count(func.distinct(DailyAggregate.bag_model_id))).where(
                DailyAggregate.observation_date == latest_date
            )
        )
        run_count = session.scalar(select(func.count()).select_from(AggregateRun))
        rows = session.scalars(
            select(DailyAggregate).where(DailyAggregate.observation_date == latest_date)
        ).all()

    if bags_with_rows != bag_count:
        raise SystemExit(f"Expected aggregate rows for {bag_count} bags, got {bags_with_rows}.")
    if run_count is None or run_count < 1:
        raise SystemExit("Expected at least one aggregate_runs row.")
    thin_rows = [row for row in rows if 0 < row.matched_listing_count < MIN_LISTINGS_PER_BAND]
    if not thin_rows:
        raise SystemExit("Expected at least one thin aggregate row.")
    for row in thin_rows:
        if row.median_asking_price is not None:
            raise SystemExit("Thin aggregate row has non-null price fields.")
    for row in rows:
        if row.matched_listing_count >= MIN_LISTINGS_PER_BAND:
            if row.p25_asking_price is None or row.median_asking_price is None or row.p75_asking_price is None:
                raise SystemExit("Priced aggregate row has null price fields.")
            if not row.p25_asking_price <= row.median_asking_price <= row.p75_asking_price:
                raise SystemExit("Priced aggregate row violates p25 <= median <= p75.")

    print(f"aggregates verified: date={latest_date} rows={len(rows)} runs={run_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
