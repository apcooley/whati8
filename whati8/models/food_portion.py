"""
FoodPortion model for household measures and portion sizes.

Each food can have multiple portion definitions (e.g., "1 cup", "1 tablespoon", "1 large egg").
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from whati8.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from whati8.models.food import Food


class FoodPortion(Base, TimestampMixin):
    """
    Household measure for a food (e.g., "1 cup", "1 tablespoon", "1 large egg").

    USDA provides multiple portion sizes for most foods. This allows users to
    select more intuitive units than grams or milliliters.
    """

    __tablename__ = "food_portions"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Foreign key (index created via __table_args__)
    food_id: Mapped[int] = mapped_column(
        ForeignKey("foods.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Portion details
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )  # e.g., 1.0, 2.0, 0.5
    unit_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )  # e.g., "cup", "tablespoon", "piece", "large"
    unit_abbreviation: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )  # e.g., "cup", "tbsp", "lg"
    gram_weight: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )  # gram equivalent, e.g., 240.0
    modifier: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )  # e.g., "sifted", "chopped", optional
    portion_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )  # full description if available
    sequence_number: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )  # for ordering portions

    # Relationship
    food: Mapped["Food"] = relationship(back_populates="portions")

    # Indexes
    __table_args__ = (
        Index("ix_food_portions_food_id", "food_id"),
        Index("ix_food_portions_sequence", "food_id", "sequence_number"),
    )

    def __repr__(self) -> str:
        modifier_str = f" {self.modifier}" if self.modifier else ""
        unit_str = self.unit_abbreviation or self.unit_name
        return f"<FoodPortion(id={self.id}, food_id={self.food_id}, amount={self.amount} {unit_str}{modifier_str}, {self.gram_weight}g)>"
