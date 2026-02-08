"""
Nutrient model for flexible nutrition tracking.

Defines standard nutrients (calories, protein, etc.) and allows
custom user-defined nutrients (Weight Watchers points, net carbs, etc.).
"""

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from whati8.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from whati8.models.food_nutrient import FoodNutrient


class Nutrient(Base, TimestampMixin):
    """
    Nutrient definition (e.g., calories, protein, saturated fat).

    Supports both standard nutrients and custom user-defined nutrients.
    Standard nutrients have user_id = NULL, custom nutrients are user-specific.
    """

    __tablename__ = "nutrients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # g, mg, kcal, points, etc.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # NULL for standard nutrients, set for user-defined nutrients
    created_by_user_id: Mapped[int | None] = mapped_column(
        nullable=True,
        index=True,
    )

    # Relationships
    food_nutrients: Mapped[list["FoodNutrient"]] = relationship(
        back_populates="nutrient",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Nutrient(id={self.id}, name='{self.name}', unit='{self.unit}')>"
