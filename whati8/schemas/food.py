"""
Pydantic schemas for food endpoints.

Defines request/response schemas for food search and retrieval.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from whati8.schemas.base import BaseORMModel


class NutrientResponse(BaseORMModel):
    """Nutrient information in a food response."""

    id: int
    name: str
    unit: str
    description: str | None = None


class FoodNutrientResponse(BaseORMModel):
    """Nutrient amount in a food."""

    nutrient: NutrientResponse
    amount_per_serving: float = Field(..., description="Amount per serving")


class FoodResponse(BaseORMModel):
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
    portions: list["PortionItem"] = Field(
        default_factory=list, description="Available portion sizes"
    )
    created_at: datetime
    updated_at: datetime


class PortionItem(BaseORMModel):
    """Portion/serving size option for a food."""

    id: int = Field(..., description="Portion ID")
    amount: float = Field(..., description="Amount (e.g., 1.0)")
    unit_name: str | None = Field(None, description="Unit name (e.g., 'cup')")
    modifier: str | None = Field(None, description="Modifier (e.g., 'large', 'sliced')")
    gram_weight: float = Field(..., description="Weight in grams")
    portion_description: str | None = Field(None, description="Human-readable description")


class FoodSearchResultItem(BaseORMModel):
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

    # Household portions
    portions: list[PortionItem] = Field(default_factory=list, description="Available portion sizes")


class FoodSearchResponse(BaseORMModel):
    """Paginated food search results."""

    query: str = Field(..., description="Search query")
    results: list[FoodSearchResultItem]
    total: int = Field(..., description="Total results found")
    limit: int = Field(..., description="Results per page")
    offset: int = Field(..., description="Result offset")


class FoodCreateRequest(BaseModel):
    """Request to create a custom food item."""

    name: str = Field(..., min_length=2, max_length=200, description="Food name (e.g., 'Vanilla Yogurt')")
    brand: str | None = Field(None, max_length=100, description="Brand name (optional)")
    serving_size: float = Field(..., gt=0, description="Serving size amount")
    unit: str = Field(default="g", max_length=20, description="Serving unit (g, oz, ml, cup, piece, etc.)")
    notes: str | None = Field(None, max_length=500, description="Additional notes (optional)")

    # Core nutrients per serving
    calories: float = Field(..., ge=0, description="Energy in kcal")
    protein: float = Field(default=0, ge=0, description="Protein in grams")
    carbs: float = Field(default=0, ge=0, description="Carbohydrates in grams")
    fat: float = Field(default=0, ge=0, description="Fat in grams")
    fiber: float | None = Field(default=None, ge=0, description="Dietary fiber in grams (optional)")
