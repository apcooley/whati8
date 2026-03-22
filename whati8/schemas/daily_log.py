"""
Pydantic schemas for daily log view and quick logging.

Defines request/response schemas for:
- Quick logging from profile foods
- Daily log view grouped by meals
- Daily nutrient summary
"""

from datetime import datetime

from pydantic import Field

from whati8.schemas.base import BaseORMModel, BaseRequestModel, BaseResponseModel


class QuickLogCreate(BaseRequestModel):
    """Request schema for quick logging from profile food."""

    user_food_id: int = Field(..., description="ID of user's profile food")
    quantity: float | None = Field(
        None, gt=0, description="Quantity (falls back to default_quantity)"
    )
    unit: str | None = Field(None, description="Unit (falls back to default_unit)")
    meal_id: int | None = Field(None, description="Meal category (falls back to default_meal_id)")
    logged_at: datetime | None = Field(None, description="Timestamp (defaults to now)")


class DailyLogEntry(BaseORMModel):
    """Single log entry in daily view."""

    id: int
    food_id: int
    food_name: str
    quantity: float
    unit: str
    logged_at: datetime
    # Computed nutrient values (from service layer)
    calories: float | None = None
    protein: float | None = None
    carbs: float | None = None
    fat: float | None = None
    fiber: float | None = None
    summary_nutrients: list[dict] = Field(default_factory=list, description="Per-log summary matching user config")


class MealGroupResponse(BaseORMModel):
    """Logs grouped by meal in daily view."""

    meal: dict = Field(..., description="Meal info (id, name, display_order)")
    logs: list[DailyLogEntry] = Field(default_factory=list, description="Log entries for this meal")


class NutrientSummary(BaseORMModel):
    """Single nutrient summary with target."""

    nutrient_id: int
    name: str
    value: float = Field(..., description="Total consumed for the day")
    target: float | None = Field(None, description="User's goal (if set)")
    unit: str


class DailyLogResponse(BaseResponseModel):
    """Daily logs grouped by meal with nutrient summary."""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    meals: list[MealGroupResponse] = Field(
        default_factory=list, description="Logs grouped by meal"
    )
    summary: dict = Field(
        default_factory=dict,
        description="Nutrient totals with targets",
    )
