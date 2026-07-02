"""foundations schema

Revision ID: 001_foundations
Revises:
Create Date: 2026-07-02
"""

from collections.abc import Sequence
from enum import Enum

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.contract import (
    AliasType,
    AuthLabel,
    ConditionBand,
    ConditionConfidence,
    ExclusionScope,
    GoldLabelVerdict,
    ListingEventType,
    PriceType,
    RejectionReason,
    ScoreClassification,
    SourceType,
    VariantKind,
)

revision: str = "001_foundations"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]


def create_pg_enum(enum_cls: type[Enum], name: str) -> None:
    postgresql.ENUM(*enum_values(enum_cls), name=name).create(op.get_bind(), checkfirst=True)


def pg_enum(enum_cls: type[Enum], name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*enum_values(enum_cls), name=name, create_type=False)


ENUMS: tuple[tuple[type[Enum], str], ...] = (
    (AliasType, "alias_type"),
    (VariantKind, "variant_kind"),
    (ExclusionScope, "exclusion_scope"),
    (RejectionReason, "rejection_reason"),
    (SourceType, "source_type"),
    (PriceType, "price_type"),
    (ConditionBand, "condition_band"),
    (ConditionConfidence, "condition_confidence"),
    (AuthLabel, "auth_label"),
    (ListingEventType, "listing_event_type"),
    (GoldLabelVerdict, "gold_label_verdict"),
    (ScoreClassification, "score_classification"),
)


def upgrade() -> None:
    for enum_cls, name in ENUMS:
        create_pg_enum(enum_cls, name)

    op.create_table(
        "brands",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("name", name="uq_brands_name"),
        sa.UniqueConstraint("slug", name="uq_brands_slug"),
    )

    op.create_table(
        "bag_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(length=180), nullable=False),
        sa.Column("era", sa.String(length=180), nullable=True),
        sa.Column("editorial_summary", sa.Text(), nullable=True),
        sa.Column("editorial_history", sa.Text(), nullable=True),
        sa.Column("editorial_condition_notes", sa.Text(), nullable=True),
        sa.Column("expected_range_note", sa.Text(), nullable=True),
        sa.Column("initial_queries", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("tracking_since", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("slug", name="uq_bag_models_slug"),
    )

    op.create_table(
        "bag_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bag_model_id", sa.Integer(), nullable=False),
        sa.Column("alias", sa.String(length=240), nullable=False),
        sa.Column("type", pg_enum(AliasType, "alias_type"), nullable=False),
        sa.ForeignKeyConstraint(["bag_model_id"], ["bag_models.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("bag_model_id", "alias", name="uq_bag_aliases_bag_alias"),
    )

    op.create_table(
        "bag_variants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bag_model_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("kind", pg_enum(VariantKind, "variant_kind"), nullable=False),
        sa.Column("attribution_confidence", sa.Text(), nullable=True),
        sa.Column("is_separate_market", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["bag_model_id"], ["bag_models.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("bag_model_id", "name", name="uq_bag_variants_bag_name"),
    )

    op.create_table(
        "exclusion_terms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bag_model_id", sa.Integer(), nullable=True),
        sa.Column("term", sa.String(length=240), nullable=False),
        sa.Column("scope", pg_enum(ExclusionScope, "exclusion_scope"), nullable=False),
        sa.Column("reason", pg_enum(RejectionReason, "rejection_reason"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "(scope = 'global' AND bag_model_id IS NULL) OR (scope = 'bag' AND bag_model_id IS NOT NULL)",
            name="ck_exclusion_terms_scope_bag_consistency",
        ),
        sa.ForeignKeyConstraint(["bag_model_id"], ["bag_models.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("scope", "bag_model_id", "term", name="uq_exclusion_terms_scope_bag_term"),
    )

    op.create_table(
        "listings_raw",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("source_type", pg_enum(SourceType, "source_type"), nullable=False),
        sa.Column("marketplace_item_id", sa.String(length=180), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("shipping_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("shipping_currency", sa.String(length=3), nullable=True),
        sa.Column("shipping_included", sa.Boolean(), nullable=True),
        sa.Column("seller_id", sa.String(length=180), nullable=True),
        sa.Column("item_url", sa.Text(), nullable=True),
        sa.Column("image_phash", sa.String(length=64), nullable=True),
        sa.Column("price_type", pg_enum(PriceType, "price_type"), nullable=False),
        sa.Column("match_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("matched_bag_model_id", sa.Integer(), nullable=True),
        sa.Column("matched_variant_id", sa.Integer(), nullable=True),
        sa.Column("condition_raw", sa.Text(), nullable=True),
        sa.Column("condition_band", pg_enum(ConditionBand, "condition_band"), nullable=True),
        sa.Column(
            "condition_confidence",
            pg_enum(ConditionConfidence, "condition_confidence"),
            nullable=False,
            server_default=ConditionConfidence.indeterminate.value,
        ),
        sa.Column(
            "auth_label",
            pg_enum(AuthLabel, "auth_label"),
            nullable=False,
            server_default=AuthLabel.authentication_status_unknown.value,
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_observed", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_observed", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "match_confidence IS NULL OR (match_confidence >= 0 AND match_confidence <= 1)",
            name="ck_listings_raw_match_confidence_range",
        ),
        sa.ForeignKeyConstraint(["matched_bag_model_id"], ["bag_models.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["matched_variant_id"], ["bag_variants.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("source", "marketplace_item_id", name="uq_listings_raw_source_item"),
    )

    op.create_table(
        "listing_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("listing_id", sa.BigInteger(), nullable=False),
        sa.Column("type", pg_enum(ListingEventType, "listing_event_type"), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["listing_id"], ["listings_raw.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "daily_aggregates",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("bag_model_id", sa.Integer(), nullable=False),
        sa.Column("variant_id", sa.Integer(), nullable=True),
        sa.Column("condition_band", pg_enum(ConditionBand, "condition_band"), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("active_listing_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("new_listing_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("ended_listing_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("possible_relist_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("median_asking_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("p25_asking_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("p75_asking_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("median_total_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("matched_listing_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("average_match_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["bag_model_id"], ["bag_models.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variant_id"], ["bag_variants.id"], ondelete="SET NULL"),
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_daily_aggregates_bag_variant_band_date
        ON daily_aggregates (bag_model_id, variant_id, condition_band, observation_date)
        NULLS NOT DISTINCT
        """
    )

    op.create_table(
        "manual_comps",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("bag_model_id", sa.Integer(), nullable=False),
        sa.Column("variant_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=160), nullable=True),
        sa.Column("source_type", pg_enum(SourceType, "source_type"), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entered_by", sa.String(length=160), nullable=True),
        sa.Column("listing_url", sa.Text(), nullable=True),
        sa.Column("sold_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("price_type", pg_enum(PriceType, "price_type"), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("shipping_included", sa.Boolean(), nullable=True),
        sa.Column("match_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("condition_raw", sa.Text(), nullable=True),
        sa.Column("condition_band", pg_enum(ConditionBand, "condition_band"), nullable=True),
        sa.Column(
            "condition_confidence",
            pg_enum(ConditionConfidence, "condition_confidence"),
            nullable=False,
            server_default=ConditionConfidence.indeterminate.value,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("source IS NOT NULL AND btrim(source) <> ''", name="ck_manual_comps_source_required"),
        sa.CheckConstraint("observed_at IS NOT NULL", name="ck_manual_comps_observed_at_required"),
        sa.CheckConstraint("condition_band IS NOT NULL", name="ck_manual_comps_condition_required"),
        sa.CheckConstraint(
            "match_confidence IS NULL OR (match_confidence >= 0 AND match_confidence <= 1)",
            name="ck_manual_comps_match_confidence_range",
        ),
        sa.ForeignKeyConstraint(["bag_model_id"], ["bag_models.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variant_id"], ["bag_variants.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "gold_labels",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("listing_id", sa.BigInteger(), nullable=True),
        sa.Column("marketplace_item_id", sa.String(length=180), nullable=True),
        sa.Column("verdict", pg_enum(GoldLabelVerdict, "gold_label_verdict"), nullable=False),
        sa.Column("rejection_reason", pg_enum(RejectionReason, "rejection_reason"), nullable=True),
        sa.Column("accepted_variant_id", sa.Integer(), nullable=True),
        sa.Column("color_family", sa.String(length=120), nullable=True),
        sa.Column("condition_band", pg_enum(ConditionBand, "condition_band"), nullable=True),
        sa.Column("strap_included", sa.Boolean(), nullable=True),
        sa.Column("lock_included", sa.Boolean(), nullable=True),
        sa.Column("key_included", sa.Boolean(), nullable=True),
        sa.Column("dustbag_included", sa.Boolean(), nullable=True),
        sa.Column("cards_included", sa.Boolean(), nullable=True),
        sa.Column("labeled_by", sa.String(length=160), nullable=True),
        sa.Column("labeled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["accepted_variant_id"], ["bag_variants.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["listing_id"], ["listings_raw.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "score_daily",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("bag_model_id", sa.Integer(), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("search_component_value", sa.Numeric(6, 2), nullable=True),
        sa.Column("search_eligible", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("search_weight_used", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("inventory_component_value", sa.Numeric(6, 2), nullable=True),
        sa.Column("inventory_eligible", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("inventory_weight_used", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("price_component_value", sa.Numeric(6, 2), nullable=True),
        sa.Column("price_eligible", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("price_weight_used", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("breadth_component_value", sa.Numeric(6, 2), nullable=True),
        sa.Column("breadth_eligible", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("breadth_weight_used", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("turnover_component_value", sa.Numeric(6, 2), nullable=True),
        sa.Column("turnover_eligible", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("turnover_weight_used", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("raw_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("smoothed_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("confidence_raw", sa.Numeric(5, 4), nullable=True),
        sa.Column("classification", pg_enum(ScoreClassification, "score_classification"), nullable=True),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("component_trace", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["bag_model_id"], ["bag_models.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("bag_model_id", "observation_date", name="uq_score_daily_bag_date"),
    )


def downgrade() -> None:
    op.drop_table("score_daily")
    op.drop_table("gold_labels")
    op.drop_table("manual_comps")
    op.drop_index("uq_daily_aggregates_bag_variant_band_date", table_name="daily_aggregates")
    op.drop_table("daily_aggregates")
    op.drop_table("listing_events")
    op.drop_table("listings_raw")
    op.drop_table("exclusion_terms")
    op.drop_table("bag_variants")
    op.drop_table("bag_aliases")
    op.drop_table("bag_models")
    op.drop_table("brands")

    for enum_cls, name in reversed(ENUMS):
        postgresql.ENUM(*enum_values(enum_cls), name=name).drop(op.get_bind(), checkfirst=True)
