"""
Password hashing and JWT creation/verification - the two cryptographic
primitives Phase 3 needs. Kept separate from the route handlers and from
the Depends() guard so each file has exactly one job:
  security.py      -> "how do we hash/verify/sign" (pure functions)
  schemas.py        -> "what does a request/response look like"
  dependencies.py   -> "given a request, who is the caller"
  routes/auth.py     -> "what happens on POST /signup and /login"
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Turn a plaintext password into a one-way bcrypt hash. The plaintext
    is never stored or logged anywhere else in the codebase."""
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a login attempt's plaintext password against the stored hash."""
    return _pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str) -> str:
    """Issue a signed JWT for `subject` (the user's id). The token itself
    carries the claim, so no server-side session table is needed to know
    who a request is from - only to verify the signature is ours."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Verify a JWT's signature and expiry, return the user id it encodes,
    or None if the token is invalid, expired, or tampered with."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
