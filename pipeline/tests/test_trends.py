from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.contract import SearchBucket, TrendQueryRole
from app.models import BagModel, Brand, SearchSignalWeekly, TrendPull
from app.settings import get_settings
from app.trends.classify import bucket_for_slope, classify_series
from app.trends.fixtures import FixtureTrendSource
from app.trends.ingest import run_weekly_trends
from app.trends.source import TrendRequest, TrendWindow, WeeklyPoint
from app.trends.stitch import stitch_windows

WEEK0 = date(2026, 1, 5)


def points(start: float, step: float, n: int, week0: date = WEEK0) -> list[WeeklyPoint]:
    return [WeeklyPoint(week=week0 + timedelta(days=7 * i), value=start + step * i) for i in range(n)]


# --- pure: bucket thresholds -------------------------------------------------


def test_bucket_thresholds() -> None:
    assert bucket_for_slope(3.0) == SearchBucket.strong_up
    assert bucket_for_slope(1.0) == SearchBucket.up
    assert bucket_for_slope(0.0) == SearchBucket.flat
    assert bucket_for_slope(-1.0) == SearchBucket.down
    assert bucket_for_slope(-3.0) == SearchBucket.strong_down


# --- pure: stitch rescales a half-scale overlapping window -------------------


def test_stitch_rescales_and_extends() -> None:
    base = TrendWindow(
        role=TrendQueryRole.canonical,
        query_text="q",
        anchor_term="handbag",
        window_start=WEEK0,
        window_end=WEEK0 + timedelta(days=7 * 9),
        points=points(40, 2.0, 10),  # 40..58
    )
    # Overlaps weeks 8,9 at half scale; extends to weeks 10,11.
    overlap_start = WEEK0 + timedelta(days=7 * 8)
    second = TrendWindow(
        role=TrendQueryRole.canonical,
        query_text="q",
        anchor_term="handbag",
        window_start=overlap_start,
        window_end=overlap_start + timedelta(days=7 * 3),
        points=[
            WeeklyPoint(week=overlap_start + timedelta(days=7 * i), value=v)
            for i, v in enumerate([28.0, 29.0, 30.0, 31.0])  # true 56,58,60,62 at 0.5 scale
        ],
    )
    result = stitch_windows([base, second])
    assert result.windows_used == 2
    # factor ~2.0 recovered from the overlap.
    assert abs(result.rescale_factors[1] - 2.0) < 1e-6
    values = {p.week: p.value for p in result.points}
    # New weeks appear rescaled to the base scale.
    assert abs(values[overlap_start + timedelta(days=7 * 2)] - 60.0) < 1e-6
    assert abs(values[overlap_start + timedelta(days=7 * 3)] - 62.0) < 1e-6


# --- pure: classify alias agreement / low volume / short series --------------


def test_classify_flags_alias_disagreement() -> None:
    canonical = points(42, 1.3, 22)
    alias = points(64, -1.3, 22)
    signals = classify_series(canonical, alias)
    assert signals[-1].alias_agrees is False
    assert signals[-1].series_length == 22


def test_classify_flags_low_volume_and_short_series() -> None:
    canonical = points(3, 0.1, 12)
    signals = classify_series(canonical, None, low_volume_flag=True)
    assert signals[-1].low_volume is True
    assert signals[-1].series_length == 12
    assert signals[-1].alias_agrees is None


# --- fixtures on disk carry the planted gate cases ---------------------------


def _fixture_source() -> FixtureTrendSource:
    settings = get_settings()
    return FixtureTrendSource(settings.resolve_pipeline_path("fixtures/trends"))


def test_fixture_chloe_is_strong_up_with_trials_and_second_window() -> None:
    source = _fixture_source()
    windows = list(
        source.fetch(TrendRequest("chloe-paddington", "chloe paddington", "paddington bag", "handbag"))
    )
    canonical = [w for w in windows if w.role == TrendQueryRole.canonical]
    alias = [w for w in windows if w.role == TrendQueryRole.alias]
    assert len(canonical) == 2  # base + second overlapping window
    assert len(alias) == 1
    base = canonical[0]
    assert len(base.reproducibility_trials) == 24
    stitched = stitch_windows(canonical).points
    signals = classify_series(stitched, alias[0].points)
    assert signals[-1].bucket == SearchBucket.strong_up
    assert signals[-1].alias_agrees is True
    assert signals[-1].series_length == 24  # second window extended 22 -> 24 weeks


def test_fixture_dior_low_volume() -> None:
    source = _fixture_source()
    windows = list(source.fetch(TrendRequest("dior-saddle", "dior saddle bag", "dior oblique saddle", "handbag")))
    canonical = [w for w in windows if w.role == TrendQueryRole.canonical]
    signals = classify_series(canonical[0].points, None, low_volume_flag=canonical[0].low_volume)
    assert signals[-1].low_volume is True


# --- DB integration: run_weekly_trends writes signal + pull rows -------------


class _StubSource:
    source_name = "stub"

    def __init__(self, windows: list[TrendWindow]) -> None:
        self._windows = windows

    def fetch(self, request: TrendRequest):
        return self._windows


def test_run_weekly_trends_writes_rows(db_engine: Engine) -> None:
    slug = f"trend-bag-{uuid4().hex[:8]}"
    with Session(db_engine) as session:
        brand = Brand(slug=f"trend-brand-{uuid4().hex[:8]}", name=f"Trend Brand {uuid4().hex[:6]}")
        bag = BagModel(slug=slug, brand=brand, model_name="Trend Bag")
        session.add_all([brand, bag])
        session.flush()
        bag_id = bag.id

        canonical = TrendWindow(
            role=TrendQueryRole.canonical,
            query_text="trend bag",
            anchor_term="handbag",
            window_start=WEEK0,
            window_end=WEEK0 + timedelta(days=7 * 17),
            points=points(40, 2.6, 18),
            reproducibility_trials=[points(40, 2.6, 18) for _ in range(3)],
        )
        alias = TrendWindow(
            role=TrendQueryRole.alias,
            query_text="trend alias",
            anchor_term="handbag",
            window_start=WEEK0,
            window_end=WEEK0 + timedelta(days=7 * 17),
            points=points(30, 1.5, 18),
        )
        summary = run_weekly_trends(
            session, _StubSource([canonical, alias]), anchor_term="handbag", now=datetime.now(UTC)
        )
        session.commit()

        assert summary.bag_stats[slug]["latest_bucket"] == "strong_up"
        signals = session.scalars(
            select(SearchSignalWeekly).where(SearchSignalWeekly.bag_model_id == bag_id)
        ).all()
        assert len(signals) == 18
        pulls = session.scalars(select(TrendPull).where(TrendPull.bag_model_id == bag_id)).all()
        # 3 reproducibility trials + 1 base canonical + 1 alias.
        assert len(pulls) == 5

        # Re-running refreshes signals (no duplicates) and appends pulls.
        run_weekly_trends(session, _StubSource([canonical, alias]), anchor_term="handbag", now=datetime.now(UTC))
        session.commit()
        signals_again = session.scalars(
            select(SearchSignalWeekly).where(SearchSignalWeekly.bag_model_id == bag_id)
        ).all()
        assert len(signals_again) == 18

        session.execute(delete(SearchSignalWeekly).where(SearchSignalWeekly.bag_model_id == bag_id))
        session.execute(delete(TrendPull).where(TrendPull.bag_model_id == bag_id))
        session.execute(delete(BagModel).where(BagModel.id == bag_id))
        session.execute(delete(Brand).where(Brand.id == brand.id))
        session.commit()
