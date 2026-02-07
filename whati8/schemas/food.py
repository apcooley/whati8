"""
Pydantic schemas for food endpoints.

Defines request/response schemas for food search and retrieval.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class NutrientResponse(BaseModel):
    """Nutrient information in a food response."""

    id: int
    name: str
    unit: str
    description: str | None = None

    model_config = {"from_attributes": True}


class FoodNutrientResponse(BaseModel):
    """Nutrient amount in a food."""

    nutrient: NutrientResponse
    amount_per_serving: float = Field(..., description="Amount per serving")

    model_config = {"from_attributes": True}


class FoodResponse(BaseModel):
    """Full food details with nutrients."""

    id: int
    name: str
    brand: str | None = None
    serving_size: float
    unit: str
    usda_fdc_id: int | None = Field(None, description="USDA FoodData Central ID")
    created_by_user_id: int | None = Field(
        None, description="User who created (null for USDA foods)"
    )
    notes: str | None = None
    food_nutrients: list[FoodNutrientResponse] = Field(
        default_factory=list, description="Nutrients in this food"
    )
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FoodSearchResultItem(BaseModel):
    """Single food item in search results."""

    id: int
    name: str
    brand: str | None = None
    serving_size: float
    unit: str
    usda_fdc_id: int | None = None
    similarity: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Text similarity score (0-1, higher is better match)",
    )

    # Key nutrients for quick preview
    calories: float | None = None
    protein: float | None = None
    carbs: float | None = None
    fat: float | None = None

    model_config = {"from_attributes": True}


class FoodSearchResponse(BaseModel):
    """Paginated food search results."""

    query: str = Field(..., description="Search query")
    results: list[FoodSearchResultItem]
    total: int = Field(..., description="Total results found")
    limit: int = Field(..., description="Results per page")
    offset: int = Field(..., description="Result offset")

    model_config = {"from_attributes": True}
