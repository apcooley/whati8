"""Authentication service for user management and JWT tokens."""
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import jwt
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.config import settings
from whati8.models import User
from whati8.schemas.auth import UserCreate, TokenPayload

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Authentication service for user management and JWT tokens."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a plaintext password using bcrypt."""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def create_access_token(user_id: int) -> str:
        """Create a JWT access token for a user."""
        expire = datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours)
        payload = {
            "sub": str(user_id),  # Subject (user ID as string for JWT spec)
            "exp": expire,   # Expiration time
        }
        return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    @staticmethod
    def decode_token(token: str) -> TokenPayload:
        """Decode and validate a JWT token."""
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        # Convert sub back to int
        payload["sub"] = int(payload["sub"])
        return TokenPayload(**payload)

    @staticmethod
    async def create_user(db: AsyncSession, user_data: UserCreate) -> User:
        """Create a new user with hashed password."""
        # Hash password
        hashed_password = AuthService.hash_password(user_data.password)

        # Create user
        user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=hashed_password,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def get_user_by_login(db: AsyncSession, login: str) -> User | None:
        """Get user by username or email."""
        result = await db.execute(
            select(User).where(
                or_(User.username == login, User.email == login)
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
        """Get user by ID."""
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def authenticate_user(db: AsyncSession, login: str, password: str) -> User | None:
        """Authenticate user with username/email and password."""
        user = await AuthService.get_user_by_login(db, login)
        if not user:
            return None
        if not AuthService.verify_password(password, user.password_hash):
            return None
        return user
