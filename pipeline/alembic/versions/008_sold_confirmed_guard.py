"""restrict sold_confirmed to auction records

Revision ID: 008_sold_confirmed_guard
Revises: 007_score_shadow
Create Date: 2026-07-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "008_sold_confirmed_guard"
down_revision: str | None = "007_score_shadow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # data-contract §4: sold_confirmed is true ONLY for auction records.
    op.execute(
        "ALTER TABLE manual_comps ADD CONSTRAINT ck_manual_comps_sold_confirmed_auction_only "
        "CHECK (sold_confirmed = false OR source_type = 'auction_record') NOT VALID"
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_manual_comps_sold_confirmed_auction_only", "manual_comps", type_="check"
    )
