"""Simplify accounts (UI-6A): keep the avatar; remove two-factor sign-in, email codes, Google sign-in, preferences,
session device details and the security log (the user chose sign-up / sign-in / profile edit only).

Revision ID: 0005_simplify_accounts
Revises: 0004_profile_security
Create Date: 2026-10-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_simplify_accounts"
down_revision = "0004_profile_security"
branch_labels = None
depends_on = None

USER_DROPPED = ["email_verified", "totp_enabled", "totp_secret", "totp_pending_secret", "totp_last_step", "recovery_codes",
                "google_sub", "preferences"]
SESSION_DROPPED = ["user_agent", "ip", "last_seen_at"]


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    tables = insp.get_table_names()
    for name in ("account_events", "auth_codes"):
        if name in tables:
            op.drop_table(name)
    have = {c["name"] for c in insp.get_columns("users")}
    if "ix_users_google_sub" in {i["name"] for i in insp.get_indexes("users")}:
        op.drop_index("ix_users_google_sub", table_name="users")
    drop = [c for c in USER_DROPPED if c in have]
    if drop:
        with op.batch_alter_table("users") as batch:
            for c in drop:
                batch.drop_column(c)
    have = {c["name"] for c in insp.get_columns("sessions")}
    drop = [c for c in SESSION_DROPPED if c in have]
    if drop:
        with op.batch_alter_table("sessions") as batch:
            for c in drop:
                batch.drop_column(c)


def downgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(sa.Column("user_agent", sa.String(300), nullable=True))
        batch.add_column(sa.Column("ip", sa.String(64), nullable=True))
        batch.add_column(sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("totp_secret", sa.String(64), nullable=True))
        batch.add_column(sa.Column("totp_pending_secret", sa.String(64), nullable=True))
        batch.add_column(sa.Column("totp_last_step", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("recovery_codes", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("google_sub", sa.String(64), nullable=True))
        batch.add_column(sa.Column("preferences", sa.JSON(), nullable=True))
