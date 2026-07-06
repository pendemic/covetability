"""manual evidence and cultural notes

Revision ID: 006_manual_evidence
Revises: 005_catalog_editor
Create Date: 2026-07-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "006_manual_evidence"
down_revision: str | None = "005_catalog_editor"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE manual_comps ADD CONSTRAINT ck_manual_comps_entered_by_required "
        "CHECK (entered_by IS NOT NULL AND btrim(entered_by) <> '') NOT VALID"
    )
    op.execute(
        "ALTER TABLE manual_comps ADD CONSTRAINT ck_manual_comps_listing_url_required "
        "CHECK (listing_url IS NOT NULL AND btrim(listing_url) <> '') NOT VALID"
    )
    op.execute(
        "ALTER TABLE manual_comps ADD CONSTRAINT ck_manual_comps_shipping_included_required "
        "CHECK (shipping_included IS NOT NULL) NOT VALID"
    )

    op.create_table(
        "cultural_notes",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "bag_model_id",
            sa.Integer(),
            sa.ForeignKey("bag_models.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("note_date", sa.Date(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("btrim(body) <> ''", name="ck_cultural_notes_body_required"),
        sa.UniqueConstraint("bag_model_id", "note_date", name="uq_cultural_notes_bag_date"),
    )
    op.create_index("ix_cultural_notes_bag_date", "cultural_notes", ["bag_model_id", "note_date"])
    op.create_index("ix_manual_comps_bag_observed", "manual_comps", ["bag_model_id", "observed_at"])


def downgrade() -> None:
    op.drop_index("ix_manual_comps_bag_observed", table_name="manual_comps")
    op.drop_index("ix_cultural_notes_bag_date", table_name="cultural_notes")
    op.drop_table("cultural_notes")
    op.drop_constraint("ck_manual_comps_shipping_included_required", "manual_comps", type_="check")
    op.drop_constraint("ck_manual_comps_listing_url_required", "manual_comps", type_="check")
    op.drop_constraint("ck_manual_comps_entered_by_required", "manual_comps", type_="check")
