from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.contract import AliasType, ExclusionScope, RejectionReason, VariantKind
from app.models.base import Base, pg_enum


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    bag_models: Mapped[list[BagModel]] = relationship(back_populates="brand")


class BagModel(Base):
    __tablename__ = "bag_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id", ondelete="RESTRICT"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(180), nullable=False)
    era: Mapped[str | None] = mapped_column(String(180))
    editorial_summary: Mapped[str | None] = mapped_column(Text)
    editorial_history: Mapped[str | None] = mapped_column(Text)
    editorial_condition_notes: Mapped[str | None] = mapped_column(Text)
    expected_range_note: Mapped[str | None] = mapped_column(Text)
    initial_queries: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    tracking_since: Mapped[date | None] = mapped_column(Date)
    recompute_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    recompute_flagged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    brand: Mapped[Brand] = relationship(back_populates="bag_models")
    aliases: Mapped[list[BagAlias]] = relationship(back_populates="bag_model")
    variants: Mapped[list[BagVariant]] = relationship(back_populates="bag_model")
    exclusion_terms: Mapped[list[ExclusionTerm]] = relationship(back_populates="bag_model")


class BagAlias(Base):
    __tablename__ = "bag_aliases"
    __table_args__ = (UniqueConstraint("bag_model_id", "alias", name="uq_bag_aliases_bag_alias"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bag_model_id: Mapped[int] = mapped_column(
        ForeignKey("bag_models.id", ondelete="CASCADE"), nullable=False
    )
    alias: Mapped[str] = mapped_column(String(240), nullable=False)
    type: Mapped[AliasType] = mapped_column(pg_enum(AliasType, "alias_type"), nullable=False)

    bag_model: Mapped[BagModel] = relationship(back_populates="aliases")


class BagVariant(Base):
    __tablename__ = "bag_variants"
    __table_args__ = (UniqueConstraint("bag_model_id", "name", name="uq_bag_variants_bag_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bag_model_id: Mapped[int] = mapped_column(
        ForeignKey("bag_models.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    kind: Mapped[VariantKind] = mapped_column(pg_enum(VariantKind, "variant_kind"), nullable=False)
    attribution_confidence: Mapped[str | None] = mapped_column(Text)
    is_separate_market: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    bag_model: Mapped[BagModel] = relationship(back_populates="variants")


class ExclusionTerm(Base):
    __tablename__ = "exclusion_terms"
    __table_args__ = (
        CheckConstraint(
            "(scope = 'global' AND bag_model_id IS NULL) OR "
            "(scope = 'bag' AND bag_model_id IS NOT NULL)",
            name="ck_exclusion_terms_scope_bag_consistency",
        ),
        UniqueConstraint("scope", "bag_model_id", "term", name="uq_exclusion_terms_scope_bag_term"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bag_model_id: Mapped[int | None] = mapped_column(ForeignKey("bag_models.id", ondelete="CASCADE"))
    term: Mapped[str] = mapped_column(String(240), nullable=False)
    scope: Mapped[ExclusionScope] = mapped_column(
        pg_enum(ExclusionScope, "exclusion_scope"), nullable=False
    )
    reason: Mapped[RejectionReason] = mapped_column(
        pg_enum(RejectionReason, "rejection_reason"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    bag_model: Mapped[BagModel | None] = relationship(back_populates="exclusion_terms")
