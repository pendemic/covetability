"""snapshot runs and event idempotency

Revision ID: 002_snapshot_runs
Revises: 001_foundations
Create Date: 2026-07-03
"""

from collections.abc import Sequence
from enum import Enum

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.contract import IngestionMode, SnapshotRunStatus

revision: str = "002_snapshot_runs"
down_revision: str | None = "001_foundations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]


def create_pg_enum(enum_cls: type[Enum], name: str) -> None:
    postgresql.ENUM(*enum_values(enum_cls), name=name).create(op.get_bind(), checkfirst=True)


def pg_enum(enum_cls: type[Enum], name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*enum_values(enum_cls), name=name, create_type=False)


ENUMS: tuple[tuple[type[Enum], str], ...] = (
    (IngestionMode, "ingestion_mode"),
    (SnapshotRunStatus, "snapshot_run_status"),
)


def upgrade() -> None:
    for enum_cls, name in ENUMS:
        create_pg_enum(enum_cls, name)

    op.create_unique_constraint(
        "uq_listing_events_listing_type_date",
        "listing_events",
        ["listing_id", "type", "event_date"],
    )

    op.create_table(
        "snapshot_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("mode", pg_enum(IngestionMode, "ingestion_mode"), nullable=False),
        sa.Column(
            "status",
            pg_enum(SnapshotRunStatus, "snapshot_run_status"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bag_counts", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ended_event_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_snapshot_runs_run_date", "snapshot_runs", ["run_date"])


def downgrade() -> None:
    op.drop_index("ix_snapshot_runs_run_date", table_name="snapshot_runs")
    op.drop_table("snapshot_runs")
    op.drop_constraint("uq_listing_events_listing_type_date", "listing_events", type_="unique")

    for enum_cls, name in reversed(ENUMS):
        postgresql.ENUM(*enum_values(enum_cls), name=name).drop(op.get_bind(), checkfirst=True)
