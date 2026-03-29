"""Shared dependencies for whati8 API."""

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose.exceptions import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.database import get_db
from whati8.models.user import User
from whati8.services.auth import AuthService

# Re-export database dependency
__all__ = ["get_db", "get_current_user"]

# HTTP Bearer token security scheme — optional so we can also check X-API-Key
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
) -> User:
    """
    Extract credentials and return the authenticated user.

    Supports three auth methods (in priority order):
    1. X-API-Key header
    2. Authorization: Bearer wi8_... (API key)
    3. Authorization: Bearer <jwt> (JWT token)

    Raises:
        HTTPException 401: Invalid credentials
        HTTPException 404: User not found in database
    """
    # Import here to avoid circular imports
    from whati8.services.api_key_service import ApiKeyService

    # 1. Check X-API-Key header
    api_key_header = request.headers.get("X-API-Key") if request else None
    if api_key_header:
        user = await ApiKeyService.validate_api_key(db, api_key_header)
        if user:
            return user
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Check Bearer token
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # 2a. API key via Bearer
    if token.startswith("wi8_"):
        user = await ApiKeyService.validate_api_key(db, token)
        if user:
            return user
        raise HTTPException(
            status_code=401,
            detail="Invalid or revoked API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2b. JWT token
    try:
        payload = AuthService.decode_token(token)
        user = await AuthService.get_user_by_id(db, payload.sub)

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return user

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
