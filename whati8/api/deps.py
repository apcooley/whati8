"""Shared dependencies for whati8 API."""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose.exceptions import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.database import get_db
from whati8.models.user import User
from whati8.services.auth import AuthService

# Re-export database dependency
__all__ = ["get_db", "get_current_user"]

# HTTP Bearer token security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Extract JWT from Authorization header, validate, and return user.

    Flow:
    1. Extract token from Bearer token in Authorization header
    2. Decode and validate JWT using AuthService.decode_token()
    3. Fetch user by ID from token payload
    4. Return user or raise 401/404

    Args:
        credentials: HTTP Bearer token credentials
        db: Database session

    Returns:
        Authenticated User object

    Raises:
        HTTPException 401: Invalid/expired token or credentials validation failed
        HTTPException 404: User not found in database
    """
    token = credentials.credentials

    try:
        # Decode and validate JWT token
        payload = AuthService.decode_token(token)

        # Fetch user from database
        user = await AuthService.get_user_by_id(db, payload.sub)

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        return user

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )
