"""covet list watch scaffold

Revision ID: 011_covet_list
Revises: 010_score_publication
Create Date: 2026-07-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "011_covet_list"
down_revision: str | None = "010_score_publication"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "covet_list_watches",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("bag_model_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bag_model_id"], ["bag_models.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", "bag_model_id", name="uq_covet_list_watches_email_bag"),
    )
    op.create_index("ix_covet_list_watches_bag", "covet_list_watches", ["bag_model_id"])


def downgrade() -> None:
    op.drop_index("ix_covet_list_watches_bag", table_name="covet_list_watches")
    op.drop_table("covet_list_watches")
