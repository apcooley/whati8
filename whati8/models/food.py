"""
Food model for USDA and custom food items.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from whati8.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from whati8.models.food_log import FoodLog
    from whati8.models.food_nutrient import FoodNutrient
    from whati8.models.recipe import RecipeIngredient
    from whati8.models.user import User


class Food(Base, TimestampMixin):
    """
    Food item from USDA database or user-created custom food.

    USDA foods have usda_fdc_id set and created_by_user_id is null.
    Custom foods have created_by_user_id set and usda_fdc_id is null.

    Nutrition values are stored in the food_nutrients table (flexible schema).
    """

    __tablename__ = "foods"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Serving size (nutrients are stored in food_nutrients table)
    serving_size: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    unit: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # USDA integration
    usda_fdc_id: Mapped[int | None] = mapped_column(
        unique=True,
        nullable=True,
        index=True,
    )

    # User ownership (null for USDA foods)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Additional details
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    created_by_user: Mapped["User | None"] = relationship(
        back_populates="foods",
    )
    food_nutrients: Mapped[list["FoodNutrient"]] = relationship(
        back_populates="food",
        cascade="all, delete-orphan",
    )
    food_logs: Mapped[list["FoodLog"]] = relationship(
        back_populates="food",
        cascade="all, delete-orphan",
    )
    recipe_ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="food",
    )

    # Indexes
    __table_args__ = (
        # GIN index for fuzzy text search using pg_trgm
        Index(
            "ix_foods_name_gin",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        # Composite index for brand + name searches
        Index("ix_foods_brand_name", "brand", "name"),
        # Index for user's custom foods
        Index("ix_foods_user_id", "created_by_user_id"),
    )

    def __repr__(self) -> str:
        brand_str = f", brand='{self.brand}'" if self.brand else ""
        return f"<Food(id={self.id}, name='{self.name}'{brand_str})>"
