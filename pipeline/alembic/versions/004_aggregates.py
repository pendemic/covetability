"""aggregate runs and condition versioning

Revision ID: 004_aggregates
Revises: 003_matching
Create Date: 2026-07-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "004_aggregates"
down_revision: str | None = "003_matching"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "listings_raw",
        sa.Column("condition_normalizer_version", sa.String(length=40), nullable=True),
    )
    op.create_index("ix_listings_raw_seller_id", "listings_raw", ["seller_id"])
    op.create_index("ix_listing_events_type_event_date", "listing_events", ["type", "event_date"])

    op.create_table(
        "aggregate_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("rows_written", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("relist_events_created", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("bag_stats", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("triggered_by", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("aggregate_runs")
    op.drop_index("ix_listing_events_type_event_date", table_name="listing_events")
    op.drop_index("ix_listings_raw_seller_id", table_name="listings_raw")
    op.drop_column("listings_raw", "condition_normalizer_version")
