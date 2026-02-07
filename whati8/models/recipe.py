"""
Recipe and RecipeIngredient models for user-created recipes.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from whati8.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from whati8.models.food import Food
    from whati8.models.user import User


class Recipe(Base, TimestampMixin):
    """
    User-created recipe composed of multiple food ingredients.

    Each recipe belongs to a user and contains multiple ingredients
    with quantities and preparation instructions.
    """

    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Foreign key
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Recipe details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="recipes")
    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeIngredient.recipe_ingredient_id",
    )

    def __repr__(self) -> str:
        return f"<Recipe(id={self.id}, name='{self.name}', user_id={self.user_id})>"


class RecipeIngredient(Base, TimestampMixin):
    """
    Individual ingredient in a recipe with quantity and unit.

    Links a recipe to a food item with specific quantity.
    The recipe_ingredient_id serves as both primary key and display order.
    """

    __tablename__ = "recipe_ingredients"

    recipe_ingredient_id: Mapped[int] = mapped_column(primary_key=True)

    # Foreign keys
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    food_id: Mapped[int] = mapped_column(
        ForeignKey("foods.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Ingredient details
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    unit: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # Relationships
    recipe: Mapped["Recipe"] = relationship(back_populates="ingredients")
    food: Mapped["Food"] = relationship(back_populates="recipe_ingredients")

    def __repr__(self) -> str:
        return f"<RecipeIngredient(id={self.recipe_ingredient_id}, recipe_id={self.recipe_id}, food_id={self.food_id}, quantity={self.quantity} {self.unit})>"
