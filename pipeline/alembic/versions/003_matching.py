"""matching state and gold label hardening

Revision ID: 003_matching
Revises: 002_snapshot_runs
Create Date: 2026-07-03
"""

from collections.abc import Sequence
from enum import Enum

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.contract import GoldLabelOrigin, MatchStatus

revision: str = "003_matching"
down_revision: str | None = "002_snapshot_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]


def create_pg_enum(enum_cls: type[Enum], name: str) -> None:
    postgresql.ENUM(*enum_values(enum_cls), name=name).create(op.get_bind(), checkfirst=True)


def pg_enum(enum_cls: type[Enum], name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*enum_values(enum_cls), name=name, create_type=False)


ENUMS: tuple[tuple[type[Enum], str], ...] = (
    (MatchStatus, "match_status"),
    (GoldLabelOrigin, "gold_label_origin"),
)


def upgrade() -> None:
    for enum_cls, name in ENUMS:
        create_pg_enum(enum_cls, name)

    op.add_column(
        "listings_raw",
        sa.Column(
            "match_status",
            pg_enum(MatchStatus, "match_status"),
            nullable=False,
            server_default=MatchStatus.pending.value,
        ),
    )
    op.add_column(
        "listings_raw",
        sa.Column("rule_trace", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column("listings_raw", sa.Column("matcher_version", sa.String(length=40), nullable=True))
    op.add_column("listings_raw", sa.Column("matched_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("listings_raw", sa.Column("candidate_bag_model_id", sa.Integer(), nullable=True))
    op.add_column("listings_raw", sa.Column("candidate_query", sa.String(length=240), nullable=True))
    op.create_foreign_key(
        "fk_listings_raw_candidate_bag_model_id",
        "listings_raw",
        "bag_models",
        ["candidate_bag_model_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_listings_raw_matched_bag_model_id", "listings_raw", ["matched_bag_model_id"])
    op.create_index("ix_listings_raw_match_status", "listings_raw", ["match_status"])
    op.create_index("ix_listings_raw_candidate_bag_model_id", "listings_raw", ["candidate_bag_model_id"])

    op.add_column("gold_labels", sa.Column("bag_model_id", sa.Integer(), nullable=False))
    op.add_column(
        "gold_labels",
        sa.Column(
            "origin",
            pg_enum(GoldLabelOrigin, "gold_label_origin"),
            nullable=False,
            server_default=GoldLabelOrigin.labeling_ui.value,
        ),
    )
    op.alter_column("gold_labels", "marketplace_item_id", existing_type=sa.String(length=180), nullable=False)
    op.create_foreign_key(
        "fk_gold_labels_bag_model_id",
        "gold_labels",
        "bag_models",
        ["bag_model_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_gold_labels_item_bag",
        "gold_labels",
        ["marketplace_item_id", "bag_model_id"],
    )
    op.create_check_constraint(
        "ck_gold_labels_verdict_reason",
        "gold_labels",
        "(verdict = 'reject' AND rejection_reason IS NOT NULL) OR "
        "(verdict = 'accept' AND rejection_reason IS NULL)",
    )
    op.create_index("ix_gold_labels_bag_model_id", "gold_labels", ["bag_model_id"])

    op.create_table(
        "match_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("matcher_version", sa.String(length=40), nullable=False),
        sa.Column("listings_considered", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status_counts", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("bag_deltas", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("threshold_exceeded", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("match_runs")
    op.drop_index("ix_gold_labels_bag_model_id", table_name="gold_labels")
    op.drop_constraint("ck_gold_labels_verdict_reason", "gold_labels", type_="check")
    op.drop_constraint("uq_gold_labels_item_bag", "gold_labels", type_="unique")
    op.drop_constraint("fk_gold_labels_bag_model_id", "gold_labels", type_="foreignkey")
    op.alter_column("gold_labels", "marketplace_item_id", existing_type=sa.String(length=180), nullable=True)
    op.drop_column("gold_labels", "origin")
    op.drop_column("gold_labels", "bag_model_id")

    op.drop_index("ix_listings_raw_candidate_bag_model_id", table_name="listings_raw")
    op.drop_index("ix_listings_raw_match_status", table_name="listings_raw")
    op.drop_index("ix_listings_raw_matched_bag_model_id", table_name="listings_raw")
    op.drop_constraint("fk_listings_raw_candidate_bag_model_id", "listings_raw", type_="foreignkey")
    op.drop_column("listings_raw", "candidate_query")
    op.drop_column("listings_raw", "candidate_bag_model_id")
    op.drop_column("listings_raw", "matched_at")
    op.drop_column("listings_raw", "matcher_version")
    op.drop_column("listings_raw", "rule_trace")
    op.drop_column("listings_raw", "match_status")

    for enum_cls, name in reversed(ENUMS):
        postgresql.ENUM(*enum_values(enum_cls), name=name).drop(op.get_bind(), checkfirst=True)
