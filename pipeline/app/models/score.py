from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.contract import (
    ConditionBand,
    ScoreClassification,
    ScoreDirection,
    SearchBucket,
    TrendQueryRole,
)
from app.models.base import Base, pg_enum


class ScoreDaily(Base):
    __tablename__ = "score_daily"
    __table_args__ = (UniqueConstraint("bag_model_id", "observation_date", name="uq_score_daily_bag_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    bag_model_id: Mapped[int] = mapped_column(ForeignKey("bag_models.id", ondelete="CASCADE"), nullable=False)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)

    search_component_value: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    search_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    search_weight_used: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, server_default=text("0"))

    inventory_component_value: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    inventory_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    inventory_weight_used: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, server_default=text("0"))

    price_component_value: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    price_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    price_weight_used: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, server_default=text("0"))

    breadth_component_value: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    breadth_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    breadth_weight_used: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, server_default=text("0"))

    turnover_component_value: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    turnover_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    turnover_weight_used: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, server_default=text("0"))

    raw_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    smoothed_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    publication_value: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    direction: Mapped[ScoreDirection | None] = mapped_column(
        pg_enum(ScoreDirection, "score_direction")
    )
    confidence_raw: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    classification: Mapped[ScoreClassification | None] = mapped_column(
        pg_enum(ScoreClassification, "score_classification")
    )
    unscored_reason: Mapped[str | None] = mapped_column(Text)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    component_trace: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class TrendPull(Base):
    """Append-only audit of every Trends pull/import (score-spec §3).

    Repeated same-window pulls accumulate so the stability gate's reproducibility
    test has real trials to measure against.
    """

    __tablename__ = "trend_pulls"
    __table_args__ = (
        Index("ix_trend_pulls_bag_role", "bag_model_id", "query_role"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    bag_model_id: Mapped[int] = mapped_column(
        ForeignKey("bag_models.id", ondelete="CASCADE"), nullable=False
    )
    query_role: Mapped[TrendQueryRole] = mapped_column(
        pg_enum(TrendQueryRole, "trend_query_role"), nullable=False
    )
    query_text: Mapped[str] = mapped_column(String(240), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    anchor_term: Mapped[str | None] = mapped_column(String(120))
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    pulled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    low_volume: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    # [{"week": "YYYY-MM-DD", "value": float}, ...] anchor-rescaled.
    weekly_points: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class SearchSignalWeekly(Base):
    """Stitched weekly search signal per bag and week (score-spec §3, §6)."""

    __tablename__ = "search_signal_weekly"
    __table_args__ = (
        UniqueConstraint("bag_model_id", "week_start", name="uq_search_signal_bag_week"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    bag_model_id: Mapped[int] = mapped_column(
        ForeignKey("bag_models.id", ondelete="CASCADE"), nullable=False
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    stitched_value: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    slope_8w: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    slope_4w: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    bucket: Mapped[SearchBucket | None] = mapped_column(pg_enum(SearchBucket, "search_bucket"))
    alias_agrees: Mapped[bool | None] = mapped_column(Boolean)
    low_volume: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    series_length: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    input_trace: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class ScorePricePoint(Base):
    """Guarded winsorized asking median used for scoring, per bag/band/day.

    Persisting this series lets the 90-day price slope survive raw-row expiry and
    encodes the 14-day same-seller repricing guard that cannot be reconstructed
    from aggregate medians after the fact (score-spec §3).
    """

    __tablename__ = "score_price_points"
    __table_args__ = (
        UniqueConstraint(
            "bag_model_id", "condition_band", "observation_date",
            name="uq_score_price_points_bag_band_date",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    bag_model_id: Mapped[int] = mapped_column(
        ForeignKey("bag_models.id", ondelete="CASCADE"), nullable=False
    )
    condition_band: Mapped[ConditionBand] = mapped_column(
        pg_enum(ConditionBand, "condition_band"), nullable=False
    )
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    guarded_median: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    listing_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    trace: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class ScoreRun(Base):
    """Audit row appended by each daily-score / recompute run."""

    __tablename__ = "score_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    mode: Mapped[str] = mapped_column(String(40), nullable=False)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    bags_scored: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    bags_unscored: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    bag_stats: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
