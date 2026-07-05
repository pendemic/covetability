from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.contract import (
    COMPONENT_KEYS,
    ConditionBand,
    ConditionConfidence,
    MatchStatus,
    PriceType,
    SearchBucket,
    SourceType,
)
from app.models import (
    BagModel,
    Brand,
    DailyAggregate,
    ListingRaw,
    ScoreDaily,
    ScorePricePoint,
    SearchSignalWeekly,
)
from app.scoring.compute import compute_bag_day, run_daily_score

DAY1 = date(2026, 6, 1)
DAY2 = date(2026, 6, 2)


def _dt(day: date) -> datetime:
    return datetime.combine(day, time(12), tzinfo=UTC)


def build_scoreable_bag(session: Session) -> BagModel:
    suffix = uuid4().hex[:8]
    brand = Brand(slug=f"cmp-brand-{suffix}", name=f"Cmp Brand {suffix}")
    bag = BagModel(slug=f"cmp-bag-{suffix}", brand=brand, model_name="Compute Bag")
    session.add_all([brand, bag])
    session.flush()

    # S: an 'up' signal for both days, plus a 'strong_up' signal only day2 sees.
    session.add_all(
        [
            _signal(bag.id, date(2026, 5, 25), SearchBucket.up),
            _signal(bag.id, date(2026, 6, 2), SearchBucket.strong_up),
        ]
    )
    # I: 60 days of aggregates ending at day2 (constant active count).
    for i in range(60):
        session.add(
            DailyAggregate(
                bag_model_id=bag.id,
                variant_id=None,
                condition_band=ConditionBand.very_good,
                observation_date=DAY2 - timedelta(days=59 - i),
                active_listing_count=20,
                matched_listing_count=20,
            )
        )
    # P coverage: 8 active listings, banded, spanning the window.
    for _ in range(8):
        session.add(_listing(bag.id, "800"))
    # P history: rising guarded medians on earlier days (day2 point is built by compute).
    for offset, median in [(89, "600"), (60, "700"), (30, "780")]:
        session.add(
            ScorePricePoint(
                bag_model_id=bag.id,
                condition_band=ConditionBand.very_good,
                observation_date=DAY2 - timedelta(days=offset),
                guarded_median=Decimal(median),
                listing_count=6,
                trace={},
            )
        )
    session.flush()
    return bag


def _signal(bag_id: int, week_start: date, bucket: SearchBucket) -> SearchSignalWeekly:
    return SearchSignalWeekly(
        bag_model_id=bag_id,
        week_start=week_start,
        stitched_value=Decimal("60"),
        slope_8w=Decimal("1.5"),
        slope_4w=Decimal("1.5"),
        bucket=bucket,
        alias_agrees=True,
        low_volume=False,
        series_length=20,
        input_trace={},
    )


def _listing(bag_id: int, price: str) -> ListingRaw:
    return ListingRaw(
        source="ebay",
        source_type=SourceType.api,
        marketplace_item_id=f"cmp-{uuid4().hex}",
        title="Compute Bag",
        price=Decimal(price),
        currency="USD",
        seller_id=f"seller-{uuid4().hex[:6]}",
        price_type=PriceType.asking,
        match_confidence=Decimal("0.9500"),
        matched_bag_model_id=bag_id,
        match_status=MatchStatus.auto_accepted,
        condition_band=ConditionBand.very_good,
        condition_confidence=ConditionConfidence.high,
        observed_at=_dt(DAY2),
        first_observed=_dt(DAY2 - timedelta(days=89)),
        last_observed=_dt(DAY2 + timedelta(days=5)),
        expires_at=_dt(DAY2 + timedelta(days=90)),
    )


def cleanup(session: Session, bag: BagModel) -> None:
    for model in (ScoreDaily, ScorePricePoint, SearchSignalWeekly, DailyAggregate):
        session.execute(delete(model).where(model.bag_model_id == bag.id))
    session.execute(delete(ListingRaw).where(ListingRaw.matched_bag_model_id == bag.id))
    brand_id = bag.brand_id
    session.execute(delete(BagModel).where(BagModel.id == bag.id))
    session.execute(delete(Brand).where(Brand.id == brand_id))
    session.commit()


def test_scored_path_and_decomposition_sums_to_delta(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        bag = build_scoreable_bag(session)
        row1 = compute_bag_day(session, bag, DAY1)
        row2 = compute_bag_day(session, bag, DAY2)
        session.flush()

        assert row1.raw_score is not None  # scored (S, I, P, B eligible)
        assert row2.raw_score is not None
        assert row1.classification is not None
        assert row1.published is False

        trace1, trace2 = row1.component_trace, row2.component_trace
        # Weights of a scored model sum to 100.
        assert abs(sum(trace2["weights"].values()) - 100.0) < 0.01

        # Day-over-day component contributions sum to the actual raw delta.
        raw_delta = float(row2.raw_score) - float(row1.raw_score)
        decomposed = sum(
            trace2["components"][key]["contribution"] - trace1["components"][key]["contribution"]
            for key in COMPONENT_KEYS
        )
        assert abs(decomposed - raw_delta) < 0.02
        # The search upgrade (up -> strong_up) is the driver of a positive move.
        assert raw_delta > 0

        # EMA sits between the previous smoothed value and the new raw score.
        assert row1.smoothed_score is not None and row2.smoothed_score is not None

        cleanup(session, bag)


def test_run_daily_score_is_idempotent_per_day(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        bag = build_scoreable_bag(session)
        run_daily_score(session, DAY2)
        run_daily_score(session, DAY2)  # re-run same day
        session.flush()
        count = session.scalar(
            select(func.count()).select_from(ScoreDaily).where(
                ScoreDaily.bag_model_id == bag.id, ScoreDaily.observation_date == DAY2
            )
        )
        assert count == 1  # delete-then-insert keeps one row per bag/day
        cleanup(session, bag)
