"""
UserSummaryNutrient model for user's daily summary preferences.

Controls which nutrients/metrics appear in the daily summary bar.
Supports both standard nutrients and custom formula-based metrics.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from whati8.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from whati8.models.nutrient import Nutrient
    from whati8.models.user import User


class UserSummaryNutrient(Base, TimestampMixin):
    """
    User's chosen nutrients/metrics for daily summary display.

    Two modes:
    1. Standard nutrient: nutrient_id set, formula null
    2. Custom formula: nutrient_id null, formula set (e.g. "round(Calories / 50, 1)")

    Formula DSL supports:
    - Nutrient references by friendly name (Calories, Protein, etc.)
    - Operators: + - * /
    - Parentheses for grouping
    - Functions: round(expr, unit), roundup(expr, unit), rounddown(expr, unit)
      where unit is the rounding increment (0.1, 0.5, 1, 5, etc.)
    """

    __tablename__ = "user_summary_nutrients"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Foreign keys
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    nutrient_id: Mapped[int | None] = mapped_column(
        ForeignKey("nutrients.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Display settings
    display_order: Mapped[int] = mapped_column(default=0, nullable=False)
    display_name: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Custom display name (overrides nutrient name)",
    )
    display_unit: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Custom display unit (overrides nutrient unit)",
    )

    # Custom formula (when nutrient_id is null)
    formula: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Formula DSL expression for computed metrics",
    )

    # Relationships
    user: Mapped["User"] = relationship()
    nutrient: Mapped["Nutrient | None"] = relationship()

    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "nutrient_id", name="uq_user_summary_nutrient"),
    )

    def __repr__(self) -> str:
        return f"<UserSummaryNutrient(id={self.id}, user_id={self.user_id}, display_name={self.display_name})>"
