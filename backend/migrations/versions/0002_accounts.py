"""Accounts (UI-2): users, sessions, and the owner of each project.

Existing projects keep owner_id = NULL until the first account is created, which adopts them
(app/services/auth_service.py).

Revision ID: 0002_accounts
Revises: 0001_baseline
Create Date: 2026-10-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_accounts"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    tables = insp.get_table_names()
    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("full_name", sa.String(120), nullable=False),
            sa.Column("email", sa.String(254), nullable=False),
            sa.Column("password_hash", sa.String(255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)
    if "sessions" not in tables:
        op.create_table(
            "sessions",
            sa.Column("token_hash", sa.String(64), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    if "owner_id" not in {c["name"] for c in insp.get_columns("projects")}:
        with op.batch_alter_table("projects") as batch:
            batch.add_column(sa.Column("owner_id", sa.String(36), nullable=True))
            batch.create_index("ix_projects_owner_id", ["owner_id"])


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.drop_index("ix_projects_owner_id")
        batch.drop_column("owner_id")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
