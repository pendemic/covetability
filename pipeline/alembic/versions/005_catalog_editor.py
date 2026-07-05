"""catalog editor recompute flags

Revision ID: 005_catalog_editor
Revises: 004_aggregates
Create Date: 2026-07-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "005_catalog_editor"
down_revision: str | None = "004_aggregates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "bag_models",
        sa.Column("recompute_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "bag_models",
        sa.Column("recompute_flagged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_listings_raw_public_lookup",
        "listings_raw",
        ["matched_bag_model_id", "match_status", "last_observed"],
    )


def downgrade() -> None:
    op.drop_index("ix_listings_raw_public_lookup", table_name="listings_raw")
    op.drop_column("bag_models", "recompute_flagged_at")
    op.drop_column("bag_models", "recompute_required")
