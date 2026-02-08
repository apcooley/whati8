"""Pydantic schemas for AI-powered food resolution."""

from pydantic import BaseModel, Field


class FoodResolveRequest(BaseModel):
    """Request to resolve natural language food input."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Natural language food description",
        examples=["I had 2 eggs and toast for breakfast"],
    )
    meal_hint: str | None = Field(
        None,
        description="Optional meal context hint",
        examples=["breakfast", "lunch", "dinner", "snack"],
    )
    max_matches_per_item: int = Field(
        3,
        ge=1,
        le=10,
        description="Maximum database matches to return per food item",
    )


class ParsedFoodItem(BaseModel):
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

    model_config = {"from_attributes": True}


class FoodMatchOption(BaseModel):
    """Database match option for a parsed food item."""

    food_id: int = Field(..., description="Database food ID")
    name: str = Field(..., description="Food name from database")
    serving_size: float = Field(..., description="Standard serving size")
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

    model_config = {"from_attributes": True}


class ResolvedFoodItem(BaseModel):
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

    model_config = {"from_attributes": True}


class MealContext(BaseModel):
    """Detected meal context from input."""

    meal_id: int | None = Field(None, description="Standard meal ID from database")
    meal_name: str | None = Field(
        None, description="Meal name", examples=["Breakfast", "Lunch", "Dinner"]
    )

    model_config = {"from_attributes": True}


class FoodResolveResponse(BaseModel):
    """Response with resolved food items and matches."""

    original_text: str = Field(..., description="Original user input")
    resolved_items: list[ResolvedFoodItem] = Field(
        ..., description="Parsed and matched food items"
    )
    meal_context: MealContext | None = Field(
        None, description="Detected meal context"
    )
    overall_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall confidence score (average of all items)",
    )
    ai_provider: str = Field(..., description="AI service used", examples=["anthropic"])

    model_config = {"from_attributes": True}
