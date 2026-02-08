"""Authentication endpoints for whati8 API."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.api.deps import get_current_user, get_db
from whati8.config import settings
from whati8.models.user import User
from whati8.schemas.auth import Token, UserCreate, UserLogin, UserResponse
from whati8.services.auth import AuthService

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    user_data: UserCreate, db: AsyncSession = Depends(get_db)
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
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)) -> Token:
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

    return Token(access_token=access_token, token_type="bearer", expires_in=expires_in)


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
