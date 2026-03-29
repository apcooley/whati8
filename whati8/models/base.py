"""
Base SQLAlchemy model and mixins.

Provides:
- Base: Declarative base for all models with naming conventions
- TimestampMixin: Automatic created_at and updated_at timestamps (timezone-aware UTC)
"""

from datetime import datetime

from sqlalchemy import MetaData, func, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Naming convention for constraints and indexes
# This ensures consistent naming across migrations
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    metadata = metadata


class TimestampMixin:
    """
    Mixin that adds created_at and updated_at timestamp fields with timezone support.

    Fields are automatically managed with UTC timezone awareness:
    - created_at: Set on insert (server default, UTC)
    - updated_at: Updated on every modification (onupdate, UTC)
    
    All timestamps are stored in PostgreSQL as TIMESTAMP WITH TIME ZONE (UTC).
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
