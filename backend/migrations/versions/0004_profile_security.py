"""Profile and security (UI-6): profile, avatar, two-factor, Google link and preferences columns on users;
session details; one-time codes; the security log.

Revision ID: 0004_profile_security
Revises: 0003_activity
Create Date: 2026-10-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_profile_security"
down_revision = "0003_activity"
branch_labels = None
depends_on = None

USER_COLUMNS = [
    sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("avatar_kind", sa.String(16), nullable=False, server_default="initials"),
    sa.Column("avatar_value", sa.String(32), nullable=True),
    sa.Column("avatar_version", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("totp_secret", sa.String(64), nullable=True),
    sa.Column("totp_pending_secret", sa.String(64), nullable=True),
    sa.Column("totp_last_step", sa.Integer(), nullable=True),
    sa.Column("recovery_codes", sa.JSON(), nullable=True),
    sa.Column("google_sub", sa.String(64), nullable=True),
    sa.Column("preferences", sa.JSON(), nullable=True),
]
SESSION_COLUMNS = [
    sa.Column("user_agent", sa.String(300), nullable=True),
    sa.Column("ip", sa.String(64), nullable=True),
    sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
]


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    have = {c["name"] for c in insp.get_columns("users")}
    missing = [c for c in USER_COLUMNS if c.name not in have]
    if missing:
        with op.batch_alter_table("users") as batch:
            for c in missing:
                batch.add_column(c)
            if "google_sub" not in have:
                batch.create_index("ix_users_google_sub", ["google_sub"])
    have = {c["name"] for c in insp.get_columns("sessions")}
    missing = [c for c in SESSION_COLUMNS if c.name not in have]
    if missing:
        with op.batch_alter_table("sessions") as batch:
            for c in missing:
                batch.add_column(c)
    tables = insp.get_table_names()
    if "auth_codes" not in tables:
        op.create_table(
            "auth_codes",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("purpose", sa.String(24), nullable=False),
            sa.Column("code_hash", sa.String(64), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_auth_codes_user_id", "auth_codes", ["user_id"])
        op.create_index("ix_auth_codes_code_hash", "auth_codes", ["code_hash"])
    if "account_events" not in tables:
        op.create_table(
            "account_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("kind", sa.String(40), nullable=False),
            sa.Column("message", sa.String(300), nullable=False),
            sa.Column("ip", sa.String(64), nullable=True),
            sa.Column("user_agent", sa.String(300), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_account_events_user_id", "account_events", ["user_id"])
        op.create_index("ix_account_events_created_at", "account_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("account_events")
    op.drop_table("auth_codes")
    with op.batch_alter_table("sessions") as batch:
        for c in SESSION_COLUMNS:
            batch.drop_column(c.name)
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_google_sub")
        for c in USER_COLUMNS:
            batch.drop_column(c.name)
