"""
The Depends() guard every protected route uses from this phase onward:
`current_user: User = Depends(get_current_user)`. FastAPI runs this
before the route body executes, so a route handler never has to manually
parse headers or decode tokens itself - if this dependency doesn't raise,
the handler can trust `current_user` is a real, verified row from Postgres.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import decode_access_token
from app.db.database import get_db
from app.db.models import User

# HTTPBearer (not OAuth2PasswordBearer) because our /login route takes a
# JSON body ({"email": ..., "password": ...}), not the OAuth2
# form-encoded "username"/"password" fields Swagger's OAuth2 login form
# expects. HTTPBearer gives Swagger's "Authorize" button a plain "paste
# your token here" field instead, which matches how this API actually
# issues and expects tokens.
bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise credentials_error

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_error

    return user
