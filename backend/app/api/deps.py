from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException
from jwt import PyJWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    settings = get_settings()
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured on the API server.")
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def get_bearer_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    parts = authorization.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        raise HTTPException(status_code=401, detail="Bearer token required")
    return parts[1].strip()


async def get_current_user_id(
    token: Annotated[str, Depends(get_bearer_token)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UUID:
    if not settings.supabase_jwt_secret:
        raise HTTPException(
            status_code=503,
            detail="SUPABASE_JWT_SECRET is not configured on the API server.",
        )
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"require": ["exp", "sub"]},
        )
    except PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token missing sub")
    return UUID(str(sub))


DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]
