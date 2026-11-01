"""Project activity (UI-3): Recent Activity and progress milestones.

Backfill: every project that already has a floor plan with rooms and walls gets a "viewed_3d" event, so projects
made before guided locking keep every module available (no one is forced through the sequence again).

Revision ID: 0003_activity
Revises: 0002_accounts
Create Date: 2026-10-06
"""
import json
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "0003_activity"
down_revision = "0002_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "project_activity" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "project_activity",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("project_id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=True),
            sa.Column("kind", sa.String(40), nullable=False),
            sa.Column("message", sa.String(300), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_project_activity_project_id", "project_activity", ["project_id"])
        op.create_index("ix_project_activity_created_at", "project_activity", ["created_at"])
    activity = sa.table("project_activity", sa.column("project_id", sa.String), sa.column("user_id", sa.String),
                        sa.column("kind", sa.String), sa.column("message", sa.String), sa.column("created_at", sa.DateTime(timezone=True)))
    done = {r[0] for r in bind.execute(sa.text("select project_id from project_activity where kind = 'viewed_3d'"))}
    rows = []
    for pid, data in bind.execute(sa.text("select id, floorplan_data from projects")):
        doc = data if isinstance(data, dict) else (json.loads(data) if data else None)
        if pid not in done and doc and doc.get("rooms") and doc.get("walls"):
            rows.append({"project_id": pid, "user_id": None, "kind": "viewed_3d",
                         "message": "All modules available (project from before guided steps)", "created_at": datetime.now(timezone.utc)})
    if rows:
        op.bulk_insert(activity, rows)


def downgrade() -> None:
    op.drop_index("ix_project_activity_created_at", table_name="project_activity")
    op.drop_index("ix_project_activity_project_id", table_name="project_activity")
    op.drop_table("project_activity")
