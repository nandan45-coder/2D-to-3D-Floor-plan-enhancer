"""Forgot password with an email code (Prompt 38A): the password_reset_codes table.

Revision ID: 0006_password_reset
Revises: 0005_simplify_accounts
Create Date: 2026-10-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_password_reset"
down_revision = "0005_simplify_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "password_reset_codes" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "password_reset_codes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("salt", sa.String(32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_password_reset_codes_user_id", "password_reset_codes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_password_reset_codes_user_id", table_name="password_reset_codes")
    op.drop_table("password_reset_codes")
