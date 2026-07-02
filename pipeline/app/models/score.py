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
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.contract import ScoreClassification
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
    confidence_raw: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    classification: Mapped[ScoreClassification | None] = mapped_column(
        pg_enum(ScoreClassification, "score_classification")
    )
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    component_trace: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
