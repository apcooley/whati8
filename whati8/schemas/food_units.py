"""Schemas for food units system."""

from enum import Enum
from pydantic import Field

from whati8.schemas.base import BaseORMModel, BaseRequestModel


class UnitType(str, Enum):
    """Standard unit types."""
    MASS = "mass"  # g, oz, lb
    VOLUME = "volume"  # cup, tbsp, tsp, fl. oz
    PIECE = "piece"  # count (e.g., 1 cookie, 2 eggs)
    OTHER = "other"  # Custom unit (food-specific)


class StandardUnit(BaseORMModel):
    """Standard unit definition."""
    unit_type: UnitType
    name: str  # "g", "cup", "piece", etc.
    display_name: str  # "Grams", "Cups", "Piece", etc.
    default_gram_weight: float | None = None  # For piece/other types


class FoodUnitOption(BaseORMModel):
    """Available unit/portion option for a food."""
    portion_id: int = Field(..., description="Database portion ID")
    food_id: int = Field(..., description="Food ID")
    unit_type: UnitType = Field(..., description="Type of unit (mass, volume, piece, other)")
    unit_name: str = Field(..., description="Unit name (g, cup, piece, scoop, etc.)")
    modifier: str | None = Field(None, description="Modifier (e.g., 'chopped')")
    amount: float = Field(..., description="Amount (e.g., 1.0 for '1 cup')")
    gram_weight: float = Field(..., description="Grams per unit")
    display_name: str = Field(..., description="Human-readable (e.g., '1 cup (240g)')")
    similarity_score: float = Field(default=0.0, description="Match score to user input (0-1)")


class FoodWithUnitsResponse(BaseORMModel):
    """Food with available units."""
    id: int
    name: str
    brand: str | None
    category: str | None
    units: list[FoodUnitOption] = Field(..., description="All available units for this food")
    recommended_unit: FoodUnitOption | None = Field(None, description="Agent-picked best unit")


class CreateFoodWithUnitsRequest(BaseRequestModel):
    """Request to create a food with units."""
    name: str = Field(..., min_length=1, max_length=255, description="Food name")
    brand: str | None = Field(None, max_length=255, description="Brand name")
    category: str | None = Field(None, max_length=255, description="Category (e.g., Dairy)")
    
    # Unit selection
    unit_type: UnitType = Field(..., description="Type of unit")
    unit_name: str = Field(..., min_length=1, max_length=50, description="Unit name (g, cup, piece, scoop, etc.)")
    amount: float = Field(..., gt=0, description="Amount per serving (e.g., 1.0 for 1 cup)")
    
    # Weight (conditional)
    gram_weight: float | None = Field(
        None,
        gt=0,
        description="Weight in grams (required for volume/piece/other, auto for mass)"
    )


class AddUnitToFoodRequest(BaseRequestModel):
    """Request to add another unit/portion to existing food."""
    food_id: int = Field(..., gt=0, description="Food to add unit to")
    unit_type: UnitType = Field(..., description="Type of unit")
    unit_name: str = Field(..., min_length=1, max_length=50, description="Unit name")
    amount: float = Field(..., gt=0, description="Amount")
    gram_weight: float = Field(..., gt=0, description="Weight in grams")
