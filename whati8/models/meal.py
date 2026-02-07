"""
Meal model for categorizing food logs (breakfast, lunch, dinner, snacks, etc.).

Supports both standard meals and user-defined custom meals.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from whati8.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from whati8.models.food_log import FoodLog
    from whati8.models.user import User


class Meal(Base, TimestampMixin):
    """
    Meal category for organizing food logs.

    Standard meals (breakfast, lunch, dinner, snack) have user_id = NULL.
    User-defined meals (brunch, tea time, etc.) are user-specific.
    """

    __tablename__ = "meals"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # NULL for standard meals, set for user-defined meals
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Display order for UI (standard meals: 1=breakfast, 2=lunch, 3=dinner, 4=snack)
    display_order: Mapped[int] = mapped_column(
        nullable=False,
        default=999,  # Custom meals default to end
    )

    # Relationships
    created_by_user: Mapped["User | None"] = relationship(back_populates="meals")
    food_logs: Mapped[list["FoodLog"]] = relationship(
        back_populates="meal",
    )

    def __repr__(self) -> str:
        user_str = f", user_id={self.created_by_user_id}" if self.created_by_user_id else ""
        return f"<Meal(id={self.id}, name='{self.name}'{user_str})>"
