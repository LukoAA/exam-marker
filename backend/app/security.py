"""Password hashing (bcrypt via passlib) and JWT creation/verification (python-jose).

SECRET_KEY comes from app.config (pydantic-settings, reads .env).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

ALGORITHM = "HS256"
# No refresh-token flow in v1 (single lecturer role) — give the access token a
# week's life rather than forcing frequent re-logins.
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, get_settings().SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str:
    """Returns the token subject (user id as str). Raises jose.JWTError if invalid/expired."""
    payload = jwt.decode(token, get_settings().SECRET_KEY, algorithms=[ALGORITHM])
    subject = payload.get("sub")
    if subject is None:
        raise JWTError("token missing subject")
    return subject
