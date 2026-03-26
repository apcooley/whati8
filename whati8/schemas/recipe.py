"""
Pydantic schemas for recipe endpoints.

Defines request/response schemas for recipe creation, retrieval, and updates.
"""

from pydantic import BaseModel, Field, field_validator

from whati8.schemas.base import BaseORMModel


class RecipeIngredientCreate(BaseModel):
    """Schema for creating a recipe ingredient."""

    food_id: int = Field(..., description="ID of the food to add")
    quantity: float = Field(..., gt=0, description="Quantity of the food")
    unit: str = Field(..., description="Unit of measurement")
    portion_description: str | None = Field(None, description="Optional portion description")


class RecipeIngredientResponse(BaseORMModel):
    """Schema for recipe ingredient in responses."""

    id: int = Field(..., description="Ingredient ID (recipe_ingredient_id)")
    food_id: int
    food_name: str = Field(..., description="Name of the ingredient food")
    quantity: float
    unit: str
    portion_description: str | None


class RecipeCreateRequest(BaseModel):
    """Schema for creating a recipe."""

    name: str = Field(..., min_length=1, description="Recipe name")
    servings: float = Field(..., gt=0, description="Number of servings")
    serving_unit: str = Field(..., min_length=1, description="Unit name for servings (e.g., 'slice', 'bowl')")
    ingredients: list[RecipeIngredientCreate] = Field(..., min_length=1, description="List of ingredients")

    @field_validator("ingredients")
    @classmethod
    def validate_ingredients(cls, v):
        """Ensure at least one ingredient."""
        if not v:
            raise ValueError("Recipe must have at least one ingredient")
        return v


class RecipeUpdateRequest(BaseModel):
    """Schema for updating recipe metadata."""

    name: str | None = Field(None, min_length=1, description="New recipe name")
    servings: float | None = Field(None, gt=0, description="New serving count")
    serving_unit: str | None = Field(None, min_length=1, description="New serving unit")


class PerServingNutrition(BaseModel):
    """Per-serving nutrition breakdown."""

    calories: float = Field(..., description="Calories per serving")
    protein_g: float = Field(..., description="Protein in grams per serving")
    carbs_g: float = Field(..., description="Carbohydrates in grams per serving")
    fat_g: float = Field(..., description="Fat in grams per serving")
    fiber_g: float = Field(..., description="Fiber in grams per serving")
    weight_g: float = Field(..., description="Weight in grams per serving")


class RecipeResponse(BaseORMModel):
    """Schema for recipe in responses."""

    id: int
    name: str
    servings: float
    serving_unit: str
    current_version: int
    food_id: int | None = Field(None, description="Current materialized food ID")
    ingredients: list[RecipeIngredientResponse] = Field(default_factory=list)
    per_serving: PerServingNutrition


class DependencyCheckResponse(BaseModel):
    """Response for dependency check endpoint."""

    allowed: bool = Field(..., description="Whether the food can be added to the recipe")
