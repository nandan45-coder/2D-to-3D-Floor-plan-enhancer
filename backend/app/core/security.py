"""
Password hashing and session tokens (UI-2).

scrypt from Python's standard library (hashlib.scrypt, RFC 7914) with a random 16-byte salt per password:
N = 2**15, r = 8, p = 1 (~32 MB, tens of milliseconds) -- in line with OWASP's scrypt guidance. Stored as
"scrypt$N$r$p$<salt b64>$<hash b64>" so the parameters can be raised later without breaking old hashes.
Verification uses a constant-time comparison.
"""
import base64
import hashlib
import hmac
import re
import secrets
from typing import Optional

_N, _R, _P, _LEN = 2 ** 15, 8, 1, 32
_MAXMEM = 64 * 1024 * 1024
# Prompt 38 (P37-12): ordinary address characters only, and a top-level domain of 2+ letters ("x@y.z" and
# "<script>@x.com" were accepted)
EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*\.[A-Za-z]{2,}$")
MIN_PASSWORD = 8


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_LEN, maxmem=_MAXMEM)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, digest = stored.split("$")
        if algo != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(password.encode("utf-8"), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p),
                                dklen=len(expected), maxmem=_MAXMEM)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


# a fixed dummy hash so a login for an unknown email costs the same time as a wrong password
DUMMY_HASH = hash_password(secrets.token_hex(8))


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii", "ignore")).hexdigest()


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def password_problem(password: str) -> Optional[str]:
    """Plain-language reason a password is too weak, or None."""
    if len(password or "") < MIN_PASSWORD:
        return f"Use at least {MIN_PASSWORD} characters."
    if len(password) > 256:
        return "Use at most 256 characters."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Use at least one letter and one number."
    return None
