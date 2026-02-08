"""
FoodLog model for tracking user food consumption.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from whati8.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from whati8.models.food import Food
    from whati8.models.meal import Meal
    from whati8.models.user import User


class FoodLog(Base, TimestampMixin):
    """
    Record of food consumed by a user.

    Tracks what food was eaten, how much, when, and which meal.
    Quantity is in the food's serving units.
    """

    __tablename__ = "food_logs"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Foreign keys
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    food_id: Mapped[int] = mapped_column(
        ForeignKey("foods.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    meal_id: Mapped[int | None] = mapped_column(
        ForeignKey("meals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Consumption details
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    logged_at: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="food_logs")
    food: Mapped["Food"] = relationship(back_populates="food_logs")
    meal: Mapped["Meal | None"] = relationship(back_populates="food_logs")

    # Indexes
    __table_args__ = (
        # Composite index for user's recent food logs (most common query)
        Index(
            "ix_food_logs_user_id_logged_at",
            "user_id",
            "logged_at",
            postgresql_using="btree",
        ),
    )

    def __repr__(self) -> str:
        return f"<FoodLog(id={self.id}, user_id={self.user_id}, food_id={self.food_id}, quantity={self.quantity})>"
