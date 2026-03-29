"""API key service for creating, validating, and revoking API keys."""

import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.models.api_key import ApiKey
from whati8.models.user import User


class ApiKeyService:
    """Service for managing API keys."""

    @staticmethod
    def _hash_key(key: str) -> str:
        """Hash an API key with SHA-256."""
        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    async def create_api_key(db: AsyncSession, user_id: int, name: str) -> dict:
        """
        Generate a new API key for a user.

        Returns a dict with id, key (plaintext, shown once), key_prefix, name, created_at.
        """
        raw_key = "wi8_" + secrets.token_urlsafe(32)
        key_hash = ApiKeyService._hash_key(raw_key)
        key_prefix = raw_key[:12]

        api_key = ApiKey(
            user_id=user_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=name,
        )
        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)

        return {
            "id": api_key.id,
            "key": raw_key,
            "key_prefix": api_key.key_prefix,
            "name": api_key.name,
            "created_at": api_key.created_at,
            "last_used_at": api_key.last_used_at,
        }

    @staticmethod
    async def validate_api_key(db: AsyncSession, key: str) -> User | None:
        """
        Validate an API key and return the associated user.

        Updates last_used_at on success. Returns None if invalid/revoked.
        """
        key_hash = ApiKeyService._hash_key(key)

        result = await db.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash)
        )
        api_key = result.scalar_one_or_none()

        if api_key is None or api_key.revoked:
            return None

        # Check expiry
        if api_key.expires_at is not None:
            now = datetime.now(timezone.utc)
            expires = api_key.expires_at
            if expires.tzinfo is None:
                from datetime import timezone as tz
                expires = expires.replace(tzinfo=tz.utc)
            if now > expires:
                return None

        # Update last_used_at
        api_key.last_used_at = datetime.now(timezone.utc)
        await db.commit()

        # Fetch user
        result = await db.execute(select(User).where(User.id == api_key.user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_api_keys(db: AsyncSession, user_id: int) -> list[dict]:
        """Return all non-revoked API keys for a user (no secrets)."""
        result = await db.execute(
            select(ApiKey).where(ApiKey.user_id == user_id, ApiKey.revoked == False)  # noqa: E712
        )
        keys = result.scalars().all()
        return [
            {
                "id": k.id,
                "name": k.name,
                "key_prefix": k.key_prefix,
                "created_at": k.created_at,
                "last_used_at": k.last_used_at,
            }
            for k in keys
        ]

    @staticmethod
    async def revoke_api_key(db: AsyncSession, user_id: int, key_id: int) -> bool:
        """Revoke an API key. Returns True if successful, False if not found/unauthorized."""
        result = await db.execute(
            select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id)
        )
        api_key = result.scalar_one_or_none()

        if api_key is None:
            return False

        api_key.revoked = True
        await db.commit()
        return True
