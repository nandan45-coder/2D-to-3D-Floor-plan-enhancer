"""Baseline: the schema before accounts (projects, estimation and sustainability settings).

Databases created before Alembic (Base.metadata.create_all, Prompts 1-32B and UI-1) already have these tables;
each is created only if it is missing, so both old and fresh databases arrive at the same state.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

JSONV = sa.JSON().with_variant(JSONB(), "postgresql")


def _missing(name: str) -> bool:
    return name not in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _missing("projects"):
        op.create_table(
            "projects",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(50), nullable=False),
            sa.Column("floorplan_data", JSONV, nullable=True),
            sa.Column("detection_status", sa.String(20), nullable=False),
            sa.Column("detection_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
    for name in ("estimation_settings", "sustainability_settings"):
        if _missing(name):
            op.create_table(
                name,
                sa.Column("project_id", sa.String(36), primary_key=True),
                sa.Column("settings", JSONV, nullable=False),
                sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            )


def downgrade() -> None:
    for name in ("sustainability_settings", "estimation_settings", "projects"):
        op.drop_table(name)
