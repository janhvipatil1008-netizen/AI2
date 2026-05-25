"""
AI² Platform — Authentication utilities

Per-user email + password auth with bcrypt hashing and signed cookies.
Cookie contains a signed user_id (itsdangerous URLSafeTimedSerializer).
"""

import os
import secrets
import warnings

import bcrypt
from dotenv import load_dotenv
from fastapi import Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from core.security_config import assert_auth_secret_set

load_dotenv()

# ── Password hashing ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ── Signed cookie tokens ──────────────────────────────────────────────────────

AUTH_COOKIE = "ai2_user_token"
_COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 days

assert_auth_secret_set()
_SECRET = os.getenv("AUTH_SECRET", "")
if not _SECRET:
    _SECRET = secrets.token_hex(32)
    warnings.warn(
        "AUTH_SECRET env var not set — using a random secret. "
        "All sessions will be invalidated on restart. "
        "Set AUTH_SECRET in your .env file for production.",
        stacklevel=1,
    )

_serializer = URLSafeTimedSerializer(_SECRET, salt="ai2-auth")


def create_auth_token(user_id: str) -> str:
    return _serializer.dumps(user_id)


def decode_auth_token(token: str, max_age: int = _COOKIE_MAX_AGE) -> str | None:
    try:
        return _serializer.loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None


def get_current_user_id(request: Request) -> str | None:
    token = request.cookies.get(AUTH_COOKIE)
    if not token:
        return None
    return decode_auth_token(token)
