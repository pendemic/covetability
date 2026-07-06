"""score shadow-mode storage

Revision ID: 007_score_shadow
Revises: 006_manual_evidence
Create Date: 2026-07-05
"""

from collections.abc import Sequence
from enum import Enum

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.contract import ConditionBand, ScoreDirection, SearchBucket, TrendQueryRole

revision: str = "007_score_shadow"
down_revision: str | None = "006_manual_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]


def create_pg_enum(enum_cls: type[Enum], name: str) -> None:
    postgresql.ENUM(*enum_values(enum_cls), name=name).create(op.get_bind(), checkfirst=True)


def pg_enum(enum_cls: type[Enum], name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*enum_values(enum_cls), name=name, create_type=False)


NEW_ENUMS: tuple[tuple[type[Enum], str], ...] = (
    (SearchBucket, "search_bucket"),
    (ScoreDirection, "score_direction"),
    (TrendQueryRole, "trend_query_role"),
)


def upgrade() -> None:
    for enum_cls, name in NEW_ENUMS:
        create_pg_enum(enum_cls, name)

    op.add_column(
        "score_daily",
        sa.Column("publication_value", sa.Numeric(6, 2), nullable=True),
    )
    op.add_column(
        "score_daily",
        sa.Column("direction", pg_enum(ScoreDirection, "score_direction"), nullable=True),
    )
    op.add_column(
        "score_daily",
        sa.Column("unscored_reason", sa.Text(), nullable=True),
    )

    op.create_table(
        "trend_pulls",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("bag_model_id", sa.Integer(), nullable=False),
        sa.Column("query_role", pg_enum(TrendQueryRole, "trend_query_role"), nullable=False),
        sa.Column("query_text", sa.String(length=240), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("anchor_term", sa.String(length=120), nullable=True),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("pulled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("low_volume", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("weekly_points", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["bag_model_id"], ["bag_models.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_trend_pulls_bag_role", "trend_pulls", ["bag_model_id", "query_role"])

    op.create_table(
        "search_signal_weekly",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("bag_model_id", sa.Integer(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("stitched_value", sa.Numeric(8, 3), nullable=True),
        sa.Column("slope_8w", sa.Numeric(8, 4), nullable=True),
        sa.Column("slope_4w", sa.Numeric(8, 4), nullable=True),
        sa.Column("bucket", pg_enum(SearchBucket, "search_bucket"), nullable=True),
        sa.Column("alias_agrees", sa.Boolean(), nullable=True),
        sa.Column("low_volume", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("series_length", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("input_trace", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["bag_model_id"], ["bag_models.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("bag_model_id", "week_start", name="uq_search_signal_bag_week"),
    )

    op.create_table(
        "score_price_points",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("bag_model_id", sa.Integer(), nullable=False),
        sa.Column("condition_band", pg_enum(ConditionBand, "condition_band"), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("guarded_median", sa.Numeric(12, 2), nullable=True),
        sa.Column("listing_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("trace", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["bag_model_id"], ["bag_models.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "bag_model_id", "condition_band", "observation_date",
            name="uq_score_price_points_bag_band_date",
        ),
    )

    op.create_table(
        "score_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("bags_scored", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("bags_unscored", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("bag_stats", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("score_runs")
    op.drop_table("score_price_points")
    op.drop_table("search_signal_weekly")
    op.drop_index("ix_trend_pulls_bag_role", table_name="trend_pulls")
    op.drop_table("trend_pulls")

    op.drop_column("score_daily", "unscored_reason")
    op.drop_column("score_daily", "direction")
    op.drop_column("score_daily", "publication_value")

    for enum_cls, name in reversed(NEW_ENUMS):
        postgresql.ENUM(*enum_values(enum_cls), name=name).drop(op.get_bind(), checkfirst=True)
