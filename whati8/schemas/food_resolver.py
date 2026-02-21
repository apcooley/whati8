"""Pydantic schemas for AI-powered food resolution."""

from pydantic import Field, field_validator

from whati8.constants import (
    AI_INPUT_MAX_LENGTH,
    AI_MAX_MATCHES_LIMIT,
    AI_MAX_MATCHES_PER_ITEM,
    AI_MEAL_HINT_MAX_LENGTH,
)
from whati8.schemas.base import BaseORMModel, BaseRequestModel


class FoodResolveRequest(BaseRequestModel):
    """Request to resolve natural language food input."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=AI_INPUT_MAX_LENGTH,
        description="Natural language food description",
        examples=["I had 2 eggs and toast for breakfast"],
    )
    meal_hint: str | None = Field(
        None,
        min_length=1,
        max_length=AI_MEAL_HINT_MAX_LENGTH,
        pattern=r"^(breakfast|lunch|dinner|snack|brunch|tea|other)$",
        description="Optional meal context hint",
        examples=["breakfast", "lunch", "dinner", "snack"],
    )
    max_matches_per_item: int = Field(
        AI_MAX_MATCHES_PER_ITEM,
        ge=1,
        le=AI_MAX_MATCHES_LIMIT,
        description="Maximum database matches to return per food item",
    )

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        """Validate text field contains meaningful content."""
        v = v.strip()
        if not v:
            raise ValueError("Food text cannot be empty or only whitespace")
        if not any(c.isalpha() for c in v):
            raise ValueError("Food text must contain at least one letter")
        return v


class ParsedFoodItem(BaseORMModel):
    """Food item extracted from natural language by AI."""

    food_name: str = Field(
        ..., description="Standardized food name", examples=["egg", "toast"]
    )
    quantity: float = Field(..., description="Numeric quantity", examples=[2.0, 1.5])
    unit: str = Field(
        ...,
        description="Measurement unit",
        examples=["pieces", "oz", "g", "cup", "tbsp", "slices"],
    )
    search_terms: list[str] = Field(
        default_factory=list,
        description="Alternative search terms for database lookup",
        examples=[["overnight oats", "oats", "oatmeal", "rolled oats"]],
    )
    original_text: str | None = Field(
        None,
        description="Original text snippet from input",
        examples=["2 eggs", "toast"],
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="AI confidence in parsing (0.0-1.0)",
        examples=[0.95, 0.75],
    )


class PortionOption(BaseORMModel):
    """A household portion option for a food (e.g., '1 cup', '1 breast')."""

    portion_id: int = Field(..., description="Database portion ID")
    amount: float = Field(..., description="Portion amount (e.g., 1.0)")
    unit_name: str = Field(..., description="Unit name (e.g., 'cup', 'breast')")
    modifier: str | None = Field(None, description="Modifier (e.g., 'chopped', 'bone removed')")
    gram_weight: float = Field(..., description="Gram equivalent for this portion")
    display_name: str = Field(..., description="Human-readable label (e.g., '1 cup (240g)')")


class FoodMatchOption(BaseORMModel):
    """Database match option for a parsed food item."""

    food_id: int = Field(..., description="Database food ID")
    name: str = Field(..., description="Food name from database")
    serving_size: float = Field(..., description="Standard serving size in grams")
    unit: str = Field(..., description="Standard serving unit")
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Text similarity score (0.0-1.0)",
    )
    calories: float | None = Field(None, description="Calories per serving")
    protein: float | None = Field(None, description="Protein (g) per serving")
    carbs: float | None = Field(None, description="Carbs (g) per serving")
    fat: float | None = Field(None, description="Fat (g) per serving")
    quantity_multiplier: float = Field(
        1.0,
        description="Multiplier to convert parsed quantity to serving size",
    )
    # Household portions
    portions: list[PortionOption] = Field(
        default_factory=list,
        description="Available household portions (e.g., '1 cup', '1 piece')",
    )
    matched_portion: PortionOption | None = Field(
        None,
        description="Best-matched portion for user's unit (if found)",
    )
    calculated_grams: float | None = Field(
        None,
        description="Calculated gram weight based on quantity × matched portion",
    )


class ResolvedFoodItem(BaseORMModel):
    """Resolved food item with parsed data and database matches."""

    parsed_item: ParsedFoodItem = Field(
        ..., description="AI-parsed food item from input"
    )
    matches: list[FoodMatchOption] = Field(
        ..., description="Database matches for this food item"
    )
    status: str = Field(
        ...,
        description="Resolution status",
        examples=["matched", "not_found", "ambiguous"],
    )


class MealContext(BaseORMModel):
    """Detected meal context from input."""

    meal_id: int | None = Field(None, description="Standard meal ID from database")
    meal_name: str | None = Field(
        None, description="Meal name", examples=["Breakfast", "Lunch", "Dinner"]
    )


class FoodResolveResponse(BaseORMModel):
    """Response with resolved food items and matches."""

    original_text: str = Field(..., description="Original user input")
    resolved_items: list[ResolvedFoodItem] = Field(
        ..., description="Parsed and matched food items"
    )
    meal_context: MealContext | None = Field(None, description="Detected meal context")
    overall_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall confidence score (average of all items)",
    )
    ai_provider: str = Field(..., description="AI service used", examples=["anthropic"])
