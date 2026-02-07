"""
UserGoal model for flexible daily nutrition targets.

Uses key-value structure to support different goal types:
- calories
- protein_g
- saturated_fat_g
- weight_watchers_points
- net_carbs_g
- etc.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from whati8.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from whati8.models.user import User


class UserGoal(Base, TimestampMixin):
    """
    Daily nutrition goal for a user (key-value structure).

    Each user can have multiple goals (e.g., calories, protein, sat fat).
    The goal_type determines what is being tracked (e.g., "calories", "protein_g").
    """

    __tablename__ = "user_goals"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Foreign key
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Goal type (e.g., "calories", "protein_g", "weight_watchers_points")
    goal_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Target value
    target_value: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    # Optional unit (e.g., "kcal", "g", "points")
    unit: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    # Relationship
    user: Mapped["User"] = relationship(back_populates="goals")

    # Constraints
    __table_args__ = (
        # Each user can have each goal type only once
        UniqueConstraint("user_id", "goal_type", name="uq_user_goal_type"),
    )

    def __repr__(self) -> str:
        unit_str = f" {self.unit}" if self.unit else ""
        return f"<UserGoal(user_id={self.user_id}, {self.goal_type}={self.target_value}{unit_str})>"
