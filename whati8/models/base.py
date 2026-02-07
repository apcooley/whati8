"""
Base SQLAlchemy model and mixins.

Provides:
- Base: Declarative base for all models with naming conventions
- TimestampMixin: Automatic created_at and updated_at timestamps
"""

from datetime import datetime

from sqlalchemy import MetaData, func
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
    Mixin that adds created_at and updated_at timestamp fields.

    Fields are automatically managed:
    - created_at: Set on insert (server default)
    - updated_at: Updated on every modification (onupdate)
    """

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
