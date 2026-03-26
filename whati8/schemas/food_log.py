"""
Pydantic schemas for food log endpoints.

Defines request/response schemas for food logging CRUD operations.
"""

from datetime import date, datetime

from pydantic import Field, field_validator, model_validator

from whati8.constants import FOOD_LOG_NOTES_MAX_LENGTH
from whati8.schemas.base import BaseORMModel, BaseRequestModel, BaseResponseModel
from whati8.schemas.food import FoodResponse


class MealResponse(BaseORMModel):
    """Basic meal information."""

    id: int
    name: str
    display_order: int


class FoodLogCreate(BaseRequestModel):
    """Request schema for creating a food log entry."""

    food_id: int = Field(..., description="ID of the food consumed")
    meal_id: int | None = Field(None, description="ID of the meal category (optional)")
    quantity: float = Field(
        ..., gt=0, description="Quantity consumed (in food's serving units)"
    )
    logged_at: datetime = Field(..., description="Timestamp when food was consumed")
    notes: str | None = Field(
        None,
        max_length=FOOD_LOG_NOTES_MAX_LENGTH,
        description="Optional notes about this food log",
    )

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, v: str | None) -> str | None:
        """Strip whitespace from notes."""
        return v.strip() if v else None


class FoodLogUpdate(BaseRequestModel):
    """Request schema for updating a food log entry (all fields optional)."""

    food_id: int | None = Field(None, description="ID of the food consumed")
    meal_id: int | None = Field(None, description="ID of the meal category")
    unit: str | None = Field(None, description="Unit/portion for this log")
    quantity: float | None = Field(
        None, gt=0, description="Quantity consumed (in food's serving units)"
    )
    logged_at: datetime | None = Field(
        None, description="Timestamp when food was consumed"
    )
    notes: str | None = Field(
        None,
        max_length=FOOD_LOG_NOTES_MAX_LENGTH,
        description="Optional notes about this food log",
    )

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, v: str | None) -> str | None:
        """Strip whitespace from notes."""
        return v.strip() if v else None


class FoodLogResponse(BaseORMModel):
    """Response schema for a food log entry with full details."""

    id: int
    user_id: int
    food_id: int
    meal_id: int | None
    quantity: float
    unit: str | None = None
    logged_at: datetime
    notes: str | None
    created_at: datetime
    updated_at: datetime

    # Nested relationships with full details
    food: FoodResponse = Field(..., description="Full food details with nutrients")
    meal: MealResponse | None = Field(None, description="Meal category details")


class FoodLogListResponse(BaseResponseModel):
    """Paginated list of food log entries."""

    logs: list[FoodLogResponse] = Field(..., description="List of food log entries")
    total: int = Field(..., description="Total number of logs matching filters")
    limit: int = Field(..., description="Results per page")
    offset: int = Field(..., description="Result offset for pagination")


class CopyLogRequest(BaseRequestModel):
    """Request schema for copying a food log to a different date."""

    target_date: date = Field(..., description="Date to copy the log to")
    meal_id: int | None = Field(
        None, description="Optional meal assignment (defaults to original meal_id)"
    )


class MoveLogRequest(BaseRequestModel):
    """Request schema for moving a food log to a different date/meal."""

    target_date: date | None = Field(None, description="New date for the log")
    meal_id: int | None = Field(None, description="New meal assignment")

    @model_validator(mode="after")
    def at_least_one(self):
        """Validate that at least one field is provided."""
        if self.target_date is None and self.meal_id is None:
            raise ValueError("At least one of target_date or meal_id is required")
        return self


class CopyMealRequest(BaseRequestModel):
    """Request schema for copying all logs from one meal to another date."""

    source_date: date = Field(..., description="Date to copy logs from")
    source_meal_id: int = Field(..., description="Meal to copy logs from")
    target_date: date = Field(..., description="Date to copy logs to")
    target_meal_id: int | None = Field(
        None, description="Target meal assignment (defaults to source_meal_id)"
    )
