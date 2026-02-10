"""Schemas for multi-food confirmation UI."""
from pydantic import Field

from whati8.schemas.base import BaseORMModel, BaseRequestModel


class MultiFoodConfirmationItem(BaseORMModel):
    """Flattened data for a single row in the Multi-Food Confirmation UI."""

    item_id: str = Field(..., description="Unique ID for frontend keying (UUID)")
    raw_text: str = Field(..., description="Original text snippet (e.g., '2 eggs')")
    parsed_quantity: float = Field(..., description="AI-parsed numeric quantity")
    parsed_unit: str = Field(..., description="AI-parsed measurement unit")
    confidence: float = Field(..., ge=0.0, le=1.0, description="AI confidence")

    # Selected match (default/guessed)
    selected_food_id: int | None = Field(None, description="DB ID of selected food")
    selected_name: str | None = Field(None, description="Name of selected food")
    serving_size: float | None = Field(None, description="Serving size of selected food")
    serving_unit: str | None = Field(None, description="Serving unit of selected food")
    calories: float | None = Field(None, description="Calories per serving")
    protein: float | None = Field(None, description="Protein (g) per serving")
    fat: float | None = Field(None, description="Fat (g) per serving")
    fiber: float | None = Field(None, description="Fiber (g) per serving")

    # Household portions (for unit conversion)
    portions: list[dict] = Field(
        default_factory=list, description="Available household portions for this food"
    )

    # Alternatives
    alternatives: list[dict] = Field(
        default_factory=list, description="Alternative matches"
    )
    status: str = Field(..., description="matched|not_found|ambiguous")


class MultiFoodConfirmationResponse(BaseORMModel):
    """Response for multi-food confirmation form."""

    original_text: str = Field(..., description="Original user input")
    food_items: list[MultiFoodConfirmationItem] = Field(
        ..., description="Parsed food items"
    )
    guessed_meal: str | None = Field(
        None, description="AI-guessed meal (Breakfast/Lunch/Dinner/Snack)"
    )
    overall_confidence: float = Field(..., ge=0.0, le=1.0)


class FoodLogBatchEntry(BaseRequestModel):
    """Single entry for batch logging."""

    food_id: int = Field(..., gt=0, description="Selected food ID")
    quantity: float = Field(..., gt=0, description="Quantity in grams")
    meal_id: int = Field(..., gt=0, description="Meal ID (validated by FK constraint)")


class FoodLogBatchRequest(BaseRequestModel):
    """Batch food log submission."""

    entries: list[FoodLogBatchEntry] = Field(
        ..., min_length=1, description="Foods to log"
    )
    logged_at: str | None = Field(None, description="ISO timestamp, defaults to now")
