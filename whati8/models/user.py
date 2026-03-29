"""
User model for authentication and user data.
"""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from whati8.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from whati8.models.api_key import ApiKey
    from whati8.models.food import Food
    from whati8.models.food_log import FoodLog
    from whati8.models.meal import Meal
    from whati8.models.recipe import Recipe
    from whati8.models.refresh_token import RefreshToken
    from whati8.models.user_food import UserFood
    from whati8.models.user_goal import UserGoal


class User(Base, TimestampMixin):
    """
    User account for authentication and authorization.

    Each user can:
    - Create custom foods
    - Log food consumption
    - Create recipes
    - Set nutrition goals (multiple goal types)
    - Define custom meals
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    foods: Mapped[list["Food"]] = relationship(
        back_populates="created_by_user",
        cascade="all, delete-orphan",
    )
    food_logs: Mapped[list["FoodLog"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    user_foods: Mapped[list["UserFood"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    recipes: Mapped[list["Recipe"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    goals: Mapped[list["UserGoal"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    meals: Mapped[list["Meal"]] = relationship(
        back_populates="created_by_user",
        cascade="all, delete-orphan",
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}')>"
