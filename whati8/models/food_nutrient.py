"""
FoodNutrient model for many-to-many relationship between foods and nutrients.

Allows foods to have different nutrient profiles based on available data.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from whati8.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from whati8.models.food import Food
    from whati8.models.nutrient import Nutrient


class FoodNutrient(Base, TimestampMixin):
    """
    Nutrient value for a specific food (per serving).

    Junction table between Food and Nutrient with the nutrient amount.
    """

    __tablename__ = "food_nutrients"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Foreign keys
    food_id: Mapped[int] = mapped_column(
        ForeignKey("foods.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nutrient_id: Mapped[int] = mapped_column(
        ForeignKey("nutrients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Nutrient amount per serving
    amount_per_serving: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    # Relationships
    food: Mapped["Food"] = relationship(back_populates="food_nutrients")
    nutrient: Mapped["Nutrient"] = relationship(back_populates="food_nutrients")

    # Constraints
    __table_args__ = (
        # Each food can have each nutrient only once
        UniqueConstraint("food_id", "nutrient_id", name="uq_food_nutrient"),
        # Composite index for efficient queries
        Index("ix_food_nutrients_food_nutrient", "food_id", "nutrient_id"),
    )

    def __repr__(self) -> str:
        return f"<FoodNutrient(food_id={self.food_id}, nutrient_id={self.nutrient_id}, amount={self.amount_per_serving})>"
