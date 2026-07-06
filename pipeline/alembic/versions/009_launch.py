"""public launch support indexes

Revision ID: 009_launch
Revises: 008_sold_confirmed_guard
Create Date: 2026-07-06
"""

from collections.abc import Sequence

from alembic import op

revision: str = "009_launch"
down_revision: str | None = "008_sold_confirmed_guard"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS ix_bag_models_slug_lower ON bag_models (lower(slug))")
    op.execute("CREATE INDEX IF NOT EXISTS ix_bag_models_model_name_lower ON bag_models (lower(model_name))")
    op.execute("CREATE INDEX IF NOT EXISTS ix_brands_name_lower ON brands (lower(name))")
    op.execute("CREATE INDEX IF NOT EXISTS ix_bag_aliases_alias_lower ON bag_aliases (lower(alias))")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_bag_aliases_alias_lower")
    op.execute("DROP INDEX IF EXISTS ix_brands_name_lower")
    op.execute("DROP INDEX IF EXISTS ix_bag_models_model_name_lower")
    op.execute("DROP INDEX IF EXISTS ix_bag_models_slug_lower")
