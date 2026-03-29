"""Authentication endpoints for whati8 API."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.api.deps import get_current_user, get_db
from whati8.api.limiter import limiter
from whati8.config import settings
from whati8.models.user import User
from whati8.schemas.api_key import ApiKeyCreate, ApiKeyCreatedResponse, ApiKeyResponse
from whati8.schemas.auth import LogoutRequest, RefreshRequest, Token, UserCreate, UserLogin, UserResponse
from whati8.services.api_key_service import ApiKeyService
from whati8.services.auth import AuthService

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit("3/minute")
async def register(
    request: Request, user_data: UserCreate, db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """
    Register a new user account.

    Request body validated by UserCreate schema:
    - username: 3-50 characters, unique
    - email: Valid email address, unique
    - password: Minimum 8 characters

    Returns created user (without password).
    Raises 409 if username/email already exists (handled by exception handler).
    """
    user = await AuthService.create_user(db, user_data)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
async def login(request: Request, credentials: UserLogin, db: AsyncSession = Depends(get_db)) -> Token:
    """
    Authenticate and receive JWT access token.

    Request body:
    - login: Username or email
    - password: User's password

    Returns JWT token with expiration time.
    Raises 401 if credentials invalid.
    """
    user = await AuthService.authenticate_user(
        db, credentials.login, credentials.password
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = AuthService.create_access_token(user.id)
    expires_in = settings.jwt_expiration_hours * 3600  # Convert to seconds
    refresh_token = await AuthService.create_refresh_token(db, user.id)

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """
    Refresh access token using a valid refresh token.

    Rotates the refresh token (old one is revoked, new one is issued).
    Returns a new access token and refresh token.
    Raises 401 if refresh token is invalid, expired, or revoked.
    """
    try:
        access_token, new_refresh_token = await AuthService.rotate_refresh_token(
            db, request.refresh_token
        )
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    expires_in = settings.jwt_expiration_hours * 3600
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        refresh_token=new_refresh_token,
    )


@router.post("/logout")
async def logout(
    request: LogoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Logout by revoking the refresh token.

    Requires a valid access token in Authorization header.
    Revokes the provided refresh token.
    """
    revoked = await AuthService.revoke_refresh_token(db, request.refresh_token, current_user.id)
    if not revoked:
        raise HTTPException(status_code=400, detail="Invalid refresh token")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """
    Get current authenticated user's information.

    Requires valid JWT token in Authorization header:
    Authorization: Bearer <token>

    Returns user profile (without password).
    Raises 401 if token invalid/expired.
    """
    return UserResponse.model_validate(current_user)


@router.post("/api-keys", response_model=ApiKeyCreatedResponse, status_code=201)
@limiter.limit("10/minute")
async def create_api_key(
    request: Request,
    key_data: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyCreatedResponse:
    """Create a new API key for the current user."""
    result = await ApiKeyService.create_api_key(db, current_user.id, key_data.name)
    return ApiKeyCreatedResponse(**result)


@router.get("/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ApiKeyResponse]:
    """List all active API keys for the current user."""
    keys = await ApiKeyService.list_api_keys(db, current_user.id)
    return [ApiKeyResponse(**k) for k in keys]


@router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Revoke an API key."""
    revoked = await ApiKeyService.revoke_api_key(db, current_user.id, key_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="API key not found")
    return Response(status_code=204)
