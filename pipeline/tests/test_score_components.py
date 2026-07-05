from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import delete
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.contract import (
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
    ListingEvent,
    ListingRaw,
    ScorePricePoint,
    SearchSignalWeekly,
)
from app.scoring.components import (
    ComponentResult,
    compute_breadth,
    compute_inventory,
    compute_price,
    compute_search,
    compute_turnover,
)
from app.scoring.price_guard import build_price_points_for_day, effective_price

DAY = date(2026, 6, 1)


def _dt(day: date) -> datetime:
    return datetime.combine(day, time(12), tzinfo=UTC)


def make_bag(session: Session) -> int:
    suffix = uuid4().hex[:8]
    brand = Brand(slug=f"sc-brand-{suffix}", name=f"SC Brand {suffix}")
    bag = BagModel(slug=f"sc-bag-{suffix}", brand=brand, model_name="Score Bag")
    session.add_all([brand, bag])
    session.flush()
    return bag.id


def cleanup(session: Session, bag_id: int) -> None:
    for model in (SearchSignalWeekly, ScorePricePoint, DailyAggregate):
        session.execute(delete(model).where(model.bag_model_id == bag_id))
    listing_ids = [
        row[0]
        for row in session.execute(
            ListingRaw.__table__.select().with_only_columns(ListingRaw.id).where(
                ListingRaw.matched_bag_model_id == bag_id
            )
        ).all()
    ]
    if listing_ids:
        session.execute(delete(ListingEvent).where(ListingEvent.listing_id.in_(listing_ids)))
        session.execute(delete(ListingRaw).where(ListingRaw.id.in_(listing_ids)))
    brand_id = session.get(BagModel, bag_id).brand_id
    session.execute(delete(BagModel).where(BagModel.id == bag_id))
    session.execute(delete(Brand).where(Brand.id == brand_id))
    session.commit()


def add_signal(session: Session, bag_id: int, *, bucket: SearchBucket, week_offset: int, **kw) -> None:
    session.add(
        SearchSignalWeekly(
            bag_model_id=bag_id,
            week_start=DAY - timedelta(days=7 * week_offset),
            stitched_value=Decimal("50"),
            slope_8w=Decimal("0"),
            slope_4w=Decimal("0"),
            bucket=bucket,
            alias_agrees=kw.get("alias_agrees", True),
            low_volume=kw.get("low_volume", False),
            series_length=kw.get("series_length", 20),
            input_trace={},
        )
    )


def add_listing(session: Session, bag_id: int, *, price: str, band: ConditionBand | None, first_day: date, last_day: date, source: str = "ebay") -> ListingRaw:
    row = ListingRaw(
        source=source,
        source_type=SourceType.api,
        marketplace_item_id=f"sc-{uuid4().hex}",
        title="Score Bag",
        price=Decimal(price),
        currency="USD",
        seller_id=f"seller-{uuid4().hex[:6]}",
        price_type=PriceType.asking,
        match_confidence=Decimal("0.9500"),
        matched_bag_model_id=bag_id,
        match_status=MatchStatus.auto_accepted,
        condition_band=band,
        condition_confidence=ConditionConfidence.high,
        observed_at=_dt(last_day),
        first_observed=_dt(first_day),
        last_observed=_dt(last_day),
        expires_at=_dt(last_day + timedelta(days=90)),
    )
    session.add(row)
    session.flush()
    return row


# --- S -----------------------------------------------------------------------


def test_search_eligible_and_gated(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        bag_id = make_bag(session)
        add_signal(session, bag_id, bucket=SearchBucket.strong_up, week_offset=0)
        session.flush()
        result = compute_search(session, bag_id, DAY)
        assert result.eligible is True
        assert result.value == 100.0
        cleanup(session, bag_id)

    for kwargs, reason_fragment in [
        ({"alias_agrees": False}, "alias"),
        ({"low_volume": True}, "volume"),
        ({"series_length": 10}, "short"),
    ]:
        with Session(db_engine) as session:
            bag_id = make_bag(session)
            add_signal(session, bag_id, bucket=SearchBucket.up, week_offset=0, **kwargs)
            session.flush()
            result = compute_search(session, bag_id, DAY)
            assert result.eligible is False
            assert reason_fragment in (result.reason or "")
            cleanup(session, bag_id)


# --- I -----------------------------------------------------------------------


def add_aggregate(session: Session, bag_id: int, day: date, active: int) -> None:
    session.add(
        DailyAggregate(
            bag_model_id=bag_id,
            variant_id=None,
            condition_band=ConditionBand.very_good,
            observation_date=day,
            active_listing_count=active,
            matched_listing_count=active,
        )
    )


def test_inventory_declining_scores_high(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        bag_id = make_bag(session)
        for i in range(60):  # 60 days, active declining 40 -> ~10
            add_aggregate(session, bag_id, DAY - timedelta(days=59 - i), active=40 - i // 2)
        session.flush()
        result = compute_inventory(session, bag_id, DAY)
        assert result.eligible is True
        assert result.value >= 65  # declining inventory scores high
        cleanup(session, bag_id)


def test_inventory_short_history_gated(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        bag_id = make_bag(session)
        for i in range(10):
            add_aggregate(session, bag_id, DAY - timedelta(days=9 - i), active=20)
        session.flush()
        result = compute_inventory(session, bag_id, DAY)
        assert result.eligible is False
        assert "history" in (result.reason or "")
        cleanup(session, bag_id)


# --- P: mix-shift guard + divergence ----------------------------------------


def add_price_point(session: Session, bag_id: int, band: ConditionBand, day: date, median: str, count: int) -> None:
    session.add(
        ScorePricePoint(
            bag_model_id=bag_id,
            condition_band=band,
            observation_date=day,
            guarded_median=Decimal(median),
            listing_count=count,
            trace={},
        )
    )


def test_price_flat_when_mix_shifts_but_band_medians_constant(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        bag_id = make_bag(session)
        # 8 active listings for coverage, all banded.
        for _ in range(8):
            add_listing(session, bag_id, price="800", band=ConditionBand.very_good,
                        first_day=DAY - timedelta(days=80), last_day=DAY)
        # Both band medians constant across 90 days; excellent count rises (mix shift).
        for i in range(0, 90, 5):
            day = DAY - timedelta(days=89 - i)
            add_price_point(session, bag_id, ConditionBand.very_good, day, "800", 6)
            add_price_point(session, bag_id, ConditionBand.excellent, day, "1500", 5 + i // 10)
        session.flush()
        inv = ComponentResult("active_inventory_momentum", 50.0, True, None, {"momentum": 0.0})
        result = compute_price(session, bag_id, DAY, inventory=inv)
        assert result.eligible is True
        assert result.value == 50.0  # flat: mix shift toward Excellent is not a price rise
        cleanup(session, bag_id)


def test_price_divergence_halves_then_excludes(db_engine: Engine) -> None:
    def build(session: Session, flat_weeks: int) -> ComponentResult:
        bag_id = make_bag(session)
        for _ in range(8):
            add_listing(session, bag_id, price="800", band=ConditionBand.very_good,
                        first_day=DAY - timedelta(days=80), last_day=DAY)
        # Rising median -> strong price value.
        for i in range(0, 90, 5):
            day = DAY - timedelta(days=89 - i)
            add_price_point(session, bag_id, ConditionBand.very_good, day, str(600 + i * 5), 6)
        for w in range(flat_weeks):
            add_signal(session, bag_id, bucket=SearchBucket.flat, week_offset=w)
        session.flush()
        inv = ComponentResult("active_inventory_momentum", 40.0, True, None, {"momentum": -0.1})
        result = compute_price(session, bag_id, DAY, inventory=inv)
        cleanup(session, bag_id)
        return result

    with Session(db_engine) as session:
        halved = build(session, flat_weeks=5)
        assert halved.eligible is True
        assert "divergence" in (halved.reason or "")
        assert halved.trace.get("halved_from") is not None
    with Session(db_engine) as session:
        excluded = build(session, flat_weeks=8)
        assert excluded.eligible is False
        assert "8+" in (excluded.reason or "")


# --- T -----------------------------------------------------------------------


def test_turnover_default_ineligible(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        bag_id = make_bag(session)
        result = compute_turnover(session, bag_id, DAY, relist_precision=None)
        assert result.eligible is False
        assert result.reason == "relist precision unvalidated"
        cleanup(session, bag_id)


# --- B -----------------------------------------------------------------------


def test_breadth_source_ladder(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        bag_id = make_bag(session)
        add_listing(session, bag_id, price="800", band=ConditionBand.very_good,
                    first_day=DAY - timedelta(days=5), last_day=DAY, source="ebay")
        session.flush()
        assert compute_breadth(session, bag_id, DAY).value == 20.0
        add_listing(session, bag_id, price="810", band=ConditionBand.very_good,
                    first_day=DAY - timedelta(days=5), last_day=DAY, source="vestiaire")
        session.flush()
        assert compute_breadth(session, bag_id, DAY).value == 45.0
        cleanup(session, bag_id)


# --- price guard: 14-day repricing rule --------------------------------------


def test_effective_price_repricing_guard() -> None:
    listing = ListingRaw(price=Decimal("2000"))
    ev1 = ListingEvent(event_date=DAY - timedelta(days=10), payload={"old_price": 800, "new_price": 1500})
    ev2 = ListingEvent(event_date=DAY - timedelta(days=3), payload={"old_price": 1500, "new_price": 2000})
    # Second reprice is 7 days after the first -> ignored by the 14-day guard.
    assert effective_price(listing, [ev1, ev2], DAY) == Decimal("1500")

    ev_far = ListingEvent(event_date=DAY - timedelta(days=30), payload={"old_price": 800, "new_price": 1500})
    ev_near = ListingEvent(event_date=DAY - timedelta(days=10), payload={"old_price": 1500, "new_price": 2000})
    # 20 days apart -> both counted.
    assert effective_price(listing, [ev_far, ev_near], DAY) == Decimal("2000")


def test_build_price_points_winsorizes_and_persists(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        bag_id = make_bag(session)
        for price in ["700", "780", "800", "820", "900", "5000"]:  # 5000 is an outlier
            add_listing(session, bag_id, price=price, band=ConditionBand.very_good,
                        first_day=DAY - timedelta(days=10), last_day=DAY)
        session.flush()
        rows = build_price_points_for_day(session, bag_id, DAY)
        assert rows == 1
        point = session.query(ScorePricePoint).filter_by(bag_model_id=bag_id).one()
        assert point.listing_count == 6
        # Winsorized median stays near the cluster, not dragged by the 5000 outlier.
        assert point.guarded_median < Decimal("1000")
        cleanup(session, bag_id)
