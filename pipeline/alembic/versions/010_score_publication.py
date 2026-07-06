"""score publication controls

Revision ID: 010_score_publication
Revises: 009_launch
Create Date: 2026-07-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "010_score_publication"
down_revision: str | None = "009_launch"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "bag_models",
        sa.Column("score_published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "bag_models",
        sa.Column("score_published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "score_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("search_weight", sa.Integer(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id = 1", name="ck_score_config_single_row"),
        sa.CheckConstraint("search_weight IN (0, 15, 25, 30)", name="ck_score_config_search_weight"),
    )


def downgrade() -> None:
    op.drop_table("score_config")
    op.drop_column("bag_models", "score_published_at")
    op.drop_column("bag_models", "score_published")
