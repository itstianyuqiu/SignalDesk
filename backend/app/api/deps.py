from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException
from jwt import PyJWKClient, PyJWTError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    settings = get_settings()
    if not settings.database_url:
        raise HTTPException(
            status_code=503,
            detail=(
                "DATABASE_URL is not configured. Create backend/.env (copy from backend/.env.example), "
                "set DATABASE_URL=postgresql+asyncpg://..., then restart the API."
            ),
        )
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


def _decode_supabase_access_token(token: str, settings: Settings) -> dict:
    """
    Verify Supabase access tokens.

    - HS256 (legacy): ``SUPABASE_JWT_SECRET``.
    - ES256 / RS256 (JWT Signing Keys): JWKS at ``{iss}/.well-known/jwks.json`` from token ``iss``.
    """
    try:
        header = jwt.get_unverified_header(token)
    except PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    alg = header.get("alg") or "HS256"
    decode_opts = {"require": ["exp", "sub"]}

    if alg == "HS256":
        if not settings.supabase_jwt_secret:
            raise HTTPException(
                status_code=503,
                detail="SUPABASE_JWT_SECRET is not configured on the API server.",
            )
        try:
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                options=decode_opts,
            )
        except PyJWTError as exc:
            raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    if alg in ("ES256", "ES384", "ES512", "RS256", "RS384", "RS512"):
        try:
            unverified: dict = jwt.decode(token, options={"verify_signature": False})
        except PyJWTError as exc:
            raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

        iss = unverified.get("iss")
        if not isinstance(iss, str) or not iss.strip():
            raise HTTPException(status_code=401, detail="Invalid token: missing iss")

        jwks_url = iss.rstrip("/") + "/.well-known/jwks.json"
        try:
            jwks_client = PyJWKClient(jwks_url, cache_keys=True)
            signing_key = jwks_client.get_signing_key_from_jwt(token)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="Could not load Supabase JWKS for this token. Check issuer URL and network.",
            ) from exc

        try:
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience="authenticated",
                issuer=iss,
                options=decode_opts,
            )
        except PyJWTError as exc:
            raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    raise HTTPException(status_code=401, detail=f"Unsupported JWT algorithm: {alg}")


async def get_current_user_id(
    token: Annotated[str, Depends(get_bearer_token)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UUID:
    payload = _decode_supabase_access_token(token, settings)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token missing sub")
    try:
        user_id = UUID(str(sub))
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token: sub is not a UUID") from None

    return user_id


async def ensure_current_user_profile(
    session: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> UUID:
    # Supabase runs a DB trigger to insert public.users; local Docker DB has no auth.users trigger.
    try:
        await session.execute(
            text("INSERT INTO public.users (id) VALUES (:id) ON CONFLICT (id) DO NOTHING"),
            {"id": user_id},
        )
        await session.commit()
    except SQLAlchemyError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=503,
            detail="Database error while ensuring user profile row.",
        ) from exc
    return user_id


DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]
CurrentUserIdEnsured = Annotated[UUID, Depends(ensure_current_user_profile)]
