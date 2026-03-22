"""
UserFood model for user's personal food library.

Links users to foods they've registered, storing personalized metadata
like nicknames, default quantities, and usage statistics.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from whati8.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from whati8.models.food import Food
    from whati8.models.meal import Meal
    from whati8.models.user import User


class UserFood(Base, TimestampMixin):
    """
    User's personal food library entry.

    Represents a user's registered food with personalized settings:
    - Custom nickname ("My protein shake")
    - Default quantity and unit for quick logging
    - Usage tracking for Recent/Frequent sections
    - Favorite status for pinning

    Distinct from:
    - `foods` table: Master catalog (USDA + custom foods)
    - `food_logs` table: Actual consumption history
    """

    __tablename__ = "user_foods"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Foreign keys
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    food_id: Mapped[int] = mapped_column(
        ForeignKey("foods.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Personalization
    nickname: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    default_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    default_meal_id: Mapped[int | None] = mapped_column(
        ForeignKey("meals.id", ondelete="SET NULL"), nullable=True
    )

    # Usage tracking
    is_favorite: Mapped[bool] = mapped_column(default=False, nullable=False)
    use_count: Mapped[int] = mapped_column(default=0, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="user_foods")
    food: Mapped["Food"] = relationship()
    default_meal: Mapped["Meal | None"] = relationship()

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("user_id", "food_id", name="uq_user_food"),
        Index("ix_user_foods_user_id", "user_id"),
        Index("ix_user_foods_user_favorite", "user_id", "is_favorite"),
        Index("ix_user_foods_user_use_count", "user_id", "use_count"),
    )

    def __repr__(self) -> str:
        return f"<UserFood(id={self.id}, user_id={self.user_id}, food_id={self.food_id}, nickname='{self.nickname}')>"
