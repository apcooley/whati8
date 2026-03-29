"""Authentication service for user management and JWT tokens."""

import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import jwt
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.config import settings
from whati8.logging_config import get_logger
from whati8.models import User
from whati8.models.refresh_token import RefreshToken
from whati8.schemas.auth import UserCreate, TokenPayload

logger = get_logger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Authentication service for user management and JWT tokens."""

    @staticmethod
    async def hash_password(password: str) -> str:
        """Hash a plaintext password using bcrypt (async to prevent blocking)."""
        return await asyncio.to_thread(pwd_context.hash, password)

    @staticmethod
    async def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash (async to prevent blocking)."""
        return await asyncio.to_thread(
            pwd_context.verify, plain_password, hashed_password
        )

    @staticmethod
    def create_access_token(user_id: int) -> str:
        """Create a JWT access token for a user."""
        expire = datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours)
        payload = {
            "sub": str(user_id),  # Subject (user ID as string for JWT spec)
            "exp": expire,  # Expiration time
        }
        return jwt.encode(
            payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
        )

    @staticmethod
    def decode_token(token: str) -> TokenPayload:
        """Decode and validate a JWT token."""
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        # Convert sub back to int
        payload["sub"] = int(payload["sub"])
        return TokenPayload(**payload)

    @staticmethod
    async def create_user(db: AsyncSession, user_data: UserCreate) -> User:
        """Create a new user with hashed password."""
        # Hash password
        hashed_password = await AuthService.hash_password(user_data.password)

        # Create user
        user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=hashed_password,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info(f"User created: {user.username} (ID: {user.id})")
        return user

    @staticmethod
    async def get_user_by_login(db: AsyncSession, login: str) -> User | None:
        """Get user by username or email."""
        result = await db.execute(
            select(User).where(or_(User.username == login, User.email == login))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
        """Get user by ID."""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def authenticate_user(
        db: AsyncSession, login: str, password: str
    ) -> User | None:
        """Authenticate user with username/email and password."""
        user = await AuthService.get_user_by_login(db, login)
        if not user:
            logger.warning(f"Login attempt with non-existent user: {login}")
            return None
        if not await AuthService.verify_password(password, user.password_hash):
            logger.warning(f"Failed login attempt for user: {login}")
            return None
        logger.info(f"User authenticated: {user.username} (ID: {user.id})")
        return user

    @staticmethod
    async def create_refresh_token(db: AsyncSession, user_id: int) -> str:
        """Create a refresh token for a user, store hash in DB, return plaintext."""
        plaintext = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(plaintext.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.refresh_token_expiration_days
        )
        refresh_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked=False,
        )
        db.add(refresh_token)
        await db.commit()
        return plaintext

    @staticmethod
    async def validate_refresh_token(
        db: AsyncSession, token: str
    ) -> RefreshToken | None:
        """Validate a refresh token; returns the RefreshToken model or None."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        rt = result.scalar_one_or_none()
        if rt is None:
            return None
        if rt.revoked:
            return None
        now = datetime.now(timezone.utc)
        if rt.expires_at.tzinfo is None:
            expires_at = rt.expires_at.replace(tzinfo=timezone.utc)
        else:
            expires_at = rt.expires_at
        if now > expires_at:
            return None
        return rt

    @staticmethod
    async def revoke_refresh_token(db: AsyncSession, token: str, user_id: int) -> bool:
        """Revoke a refresh token by marking it as revoked.
        
        Only revokes if the token belongs to the specified user (ownership check).
        Returns True if token was found and revoked, False otherwise.
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.user_id == user_id,
            )
        )
        rt = result.scalar_one_or_none()
        if rt is None:
            return False
        rt.revoked = True
        await db.commit()
        return True

    @staticmethod
    async def rotate_refresh_token(
        db: AsyncSession, old_token: str
    ) -> tuple[str, str]:
        """Rotate refresh token: revoke old, create new access + refresh tokens."""
        rt = await AuthService.validate_refresh_token(db, old_token)
        if rt is None:
            raise ValueError("Invalid or expired refresh token")
        user_id = rt.user_id
        # Revoke old token and create new one in a single transaction
        rt.revoked = True
        await db.flush()  # Don't commit yet — let create_refresh_token's commit cover both
        access_token = AuthService.create_access_token(user_id)
        new_refresh_token = await AuthService.create_refresh_token(db, user_id)
        # create_refresh_token commits, which also commits the revocation above
        return access_token, new_refresh_token
