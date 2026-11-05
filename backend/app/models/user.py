"""
User accounts and sign-in sessions (UI-2), with the avatar (UI-6).

Passwords are never stored: only a salted scrypt hash (app/core/security.py). A session is a random token kept
in an httpOnly cookie; the database stores only its SHA-256, so a leaked database does not leak live sessions,
and logging out deletes the row.
"""
import uuid
from datetime import datetime, timezone

from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)   # stored lower-case
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # UI-6 avatar: "initials" (value = #RRGGBB background or null), "preset" (value = preset key), "photo" (file on disk)
    avatar_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="initials", server_default="initials")
    avatar_value: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    avatar_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class UserSession(Base):
    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)                     # sha256 hex of the cookie token
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PasswordResetCode(Base):
    """A one-time 6-digit code sent by email to reset a password (Prompt 38A). Only a salted SHA-256 of the code is
    stored; a code works once, for 10 minutes, and dies after 5 wrong tries."""
    __tablename__ = "password_reset_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    salt: Mapped[str] = mapped_column(String(32), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
