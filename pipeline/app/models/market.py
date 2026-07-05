from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.contract import (
    AuthLabel,
    ConditionBand,
    ConditionConfidence,
    GoldLabelOrigin,
    GoldLabelVerdict,
    IngestionMode,
    ListingEventType,
    MatchStatus,
    PriceType,
    RejectionReason,
    SnapshotRunStatus,
    SourceType,
)
from app.models.base import Base, pg_enum


class ListingRaw(Base):
    __tablename__ = "listings_raw"
    __table_args__ = (
        UniqueConstraint("source", "marketplace_item_id", name="uq_listings_raw_source_item"),
        CheckConstraint(
            "match_confidence IS NULL OR (match_confidence >= 0 AND match_confidence <= 1)",
            name="ck_listings_raw_match_confidence_range",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(pg_enum(SourceType, "source_type"), nullable=False)
    marketplace_item_id: Mapped[str] = mapped_column(String(180), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    shipping_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    shipping_currency: Mapped[str | None] = mapped_column(String(3))
    shipping_included: Mapped[bool | None] = mapped_column(Boolean)
    seller_id: Mapped[str | None] = mapped_column(String(180))
    item_url: Mapped[str | None] = mapped_column(Text)
    image_phash: Mapped[str | None] = mapped_column(String(64))
    price_type: Mapped[PriceType] = mapped_column(pg_enum(PriceType, "price_type"), nullable=False)
    match_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    matched_bag_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("bag_models.id", ondelete="SET NULL")
    )
    matched_variant_id: Mapped[int | None] = mapped_column(
        ForeignKey("bag_variants.id", ondelete="SET NULL")
    )
    match_status: Mapped[MatchStatus] = mapped_column(
        pg_enum(MatchStatus, "match_status"),
        nullable=False,
        server_default=MatchStatus.pending.value,
    )
    rule_trace: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    matcher_version: Mapped[str | None] = mapped_column(String(40))
    matched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    candidate_bag_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("bag_models.id", ondelete="SET NULL")
    )
    candidate_query: Mapped[str | None] = mapped_column(String(240))
    condition_raw: Mapped[str | None] = mapped_column(Text)
    condition_band: Mapped[ConditionBand | None] = mapped_column(
        pg_enum(ConditionBand, "condition_band")
    )
    condition_confidence: Mapped[ConditionConfidence] = mapped_column(
        pg_enum(ConditionConfidence, "condition_confidence"),
        nullable=False,
        server_default=ConditionConfidence.indeterminate.value,
    )
    condition_normalizer_version: Mapped[str | None] = mapped_column(String(40))
    auth_label: Mapped[AuthLabel] = mapped_column(
        pg_enum(AuthLabel, "auth_label"),
        nullable=False,
        server_default=AuthLabel.authentication_status_unknown.value,
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_observed: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_observed: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    events: Mapped[list[ListingEvent]] = relationship(back_populates="listing")


class ListingEvent(Base):
    __tablename__ = "listing_events"
    __table_args__ = (
        UniqueConstraint("listing_id", "type", "event_date", name="uq_listing_events_listing_type_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings_raw.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[ListingEventType] = mapped_column(
        pg_enum(ListingEventType, "listing_event_type"), nullable=False
    )
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    listing: Mapped[ListingRaw] = relationship(back_populates="events")


class SnapshotRun(Base):
    __tablename__ = "snapshot_runs"
    __table_args__ = (Index("ix_snapshot_runs_run_date", "run_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    mode: Mapped[IngestionMode] = mapped_column(pg_enum(IngestionMode, "ingestion_mode"), nullable=False)
    status: Mapped[SnapshotRunStatus] = mapped_column(
        pg_enum(SnapshotRunStatus, "snapshot_run_status"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bag_counts: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    ended_event_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class DailyAggregate(Base):
    __tablename__ = "daily_aggregates"
    __table_args__ = (
        Index(
            "uq_daily_aggregates_bag_variant_band_date",
            "bag_model_id",
            "variant_id",
            "condition_band",
            "observation_date",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    bag_model_id: Mapped[int] = mapped_column(ForeignKey("bag_models.id", ondelete="CASCADE"), nullable=False)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("bag_variants.id", ondelete="SET NULL"))
    condition_band: Mapped[ConditionBand] = mapped_column(
        pg_enum(ConditionBand, "condition_band"), nullable=False
    )
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    active_listing_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    new_listing_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    ended_listing_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    possible_relist_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    median_asking_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    p25_asking_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    p75_asking_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    median_total_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    matched_listing_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    average_match_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class ManualComp(Base):
    __tablename__ = "manual_comps"
    __table_args__ = (
        CheckConstraint("source IS NOT NULL AND btrim(source) <> ''", name="ck_manual_comps_source_required"),
        CheckConstraint("observed_at IS NOT NULL", name="ck_manual_comps_observed_at_required"),
        CheckConstraint("condition_band IS NOT NULL", name="ck_manual_comps_condition_required"),
        CheckConstraint(
            "match_confidence IS NULL OR (match_confidence >= 0 AND match_confidence <= 1)",
            name="ck_manual_comps_match_confidence_range",
        ),
        CheckConstraint(
            "entered_by IS NOT NULL AND btrim(entered_by) <> ''",
            name="ck_manual_comps_entered_by_required",
        ),
        CheckConstraint(
            "listing_url IS NOT NULL AND btrim(listing_url) <> ''",
            name="ck_manual_comps_listing_url_required",
        ),
        CheckConstraint(
            "shipping_included IS NOT NULL",
            name="ck_manual_comps_shipping_included_required",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    bag_model_id: Mapped[int] = mapped_column(ForeignKey("bag_models.id", ondelete="CASCADE"), nullable=False)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("bag_variants.id", ondelete="SET NULL"))
    source: Mapped[str | None] = mapped_column(String(160))
    source_type: Mapped[SourceType] = mapped_column(pg_enum(SourceType, "source_type"), nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    entered_by: Mapped[str | None] = mapped_column(String(160))
    listing_url: Mapped[str | None] = mapped_column(Text)
    sold_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    price_type: Mapped[PriceType] = mapped_column(pg_enum(PriceType, "price_type"), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    shipping_included: Mapped[bool | None] = mapped_column(Boolean)
    match_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    condition_raw: Mapped[str | None] = mapped_column(Text)
    condition_band: Mapped[ConditionBand | None] = mapped_column(
        pg_enum(ConditionBand, "condition_band")
    )
    condition_confidence: Mapped[ConditionConfidence] = mapped_column(
        pg_enum(ConditionConfidence, "condition_confidence"),
        nullable=False,
        server_default=ConditionConfidence.indeterminate.value,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class CulturalNote(Base):
    __tablename__ = "cultural_notes"
    __table_args__ = (
        UniqueConstraint("bag_model_id", "note_date", name="uq_cultural_notes_bag_date"),
        CheckConstraint("btrim(body) <> ''", name="ck_cultural_notes_body_required"),
        Index("ix_cultural_notes_bag_date", "bag_model_id", "note_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    bag_model_id: Mapped[int] = mapped_column(ForeignKey("bag_models.id", ondelete="CASCADE"), nullable=False)
    note_date: Mapped[date] = mapped_column(Date, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class GoldLabel(Base):
    __tablename__ = "gold_labels"
    __table_args__ = (
        UniqueConstraint("marketplace_item_id", "bag_model_id", name="uq_gold_labels_item_bag"),
        CheckConstraint(
            "(verdict = 'reject' AND rejection_reason IS NOT NULL) OR "
            "(verdict = 'accept' AND rejection_reason IS NULL)",
            name="ck_gold_labels_verdict_reason",
        ),
        Index("ix_gold_labels_bag_model_id", "bag_model_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    listing_id: Mapped[int | None] = mapped_column(ForeignKey("listings_raw.id", ondelete="SET NULL"))
    marketplace_item_id: Mapped[str] = mapped_column(String(180), nullable=False)
    bag_model_id: Mapped[int] = mapped_column(ForeignKey("bag_models.id", ondelete="CASCADE"), nullable=False)
    verdict: Mapped[GoldLabelVerdict] = mapped_column(
        pg_enum(GoldLabelVerdict, "gold_label_verdict"), nullable=False
    )
    origin: Mapped[GoldLabelOrigin] = mapped_column(
        pg_enum(GoldLabelOrigin, "gold_label_origin"),
        nullable=False,
        server_default=GoldLabelOrigin.labeling_ui.value,
    )
    rejection_reason: Mapped[RejectionReason | None] = mapped_column(
        pg_enum(RejectionReason, "rejection_reason")
    )
    accepted_variant_id: Mapped[int | None] = mapped_column(ForeignKey("bag_variants.id", ondelete="SET NULL"))
    color_family: Mapped[str | None] = mapped_column(String(120))
    condition_band: Mapped[ConditionBand | None] = mapped_column(
        pg_enum(ConditionBand, "condition_band")
    )
    strap_included: Mapped[bool | None] = mapped_column(Boolean)
    lock_included: Mapped[bool | None] = mapped_column(Boolean)
    key_included: Mapped[bool | None] = mapped_column(Boolean)
    dustbag_included: Mapped[bool | None] = mapped_column(Boolean)
    cards_included: Mapped[bool | None] = mapped_column(Boolean)
    labeled_by: Mapped[str | None] = mapped_column(String(160))
    labeled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    notes: Mapped[str | None] = mapped_column(Text)


class MatchRun(Base):
    __tablename__ = "match_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    mode: Mapped[str] = mapped_column(String(40), nullable=False)
    matcher_version: Mapped[str] = mapped_column(String(40), nullable=False)
    listings_considered: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status_counts: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    bag_deltas: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    threshold_exceeded: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class AggregateRun(Base):
    __tablename__ = "aggregate_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    mode: Mapped[str] = mapped_column(String(40), nullable=False)
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    rows_written: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    relist_events_created: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    bag_stats: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    triggered_by: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
