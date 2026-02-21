# Custom Foods Feature Plan

## Overview
Allow users to create and manage their own food entries for items not in the USDA database (branded products, homemade recipes, etc.).

## Database Schema

### Existing Support
The `foods` table already has `created_by_user_id` field:
```python
class Food(Base):
    ...
    created_by_user_id: Mapped[int | None]  # NULL = USDA, set = user-created
```

### Optional Additions
Consider adding:
- `is_verified: bool = False` - For community-verified entries
- `barcode: str | None` - UPC/EAN for barcode scanning later
- `source: str | None` - "usda", "user", "openfoodfacts", etc.

## Backend Implementation

### 1. API Endpoint
**File:** `whati8/api/routers/food.py`

```python
@router.post("/", response_model=FoodResponse)
async def create_food(
    food_data: FoodCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a custom food entry."""
    food = Food(
        name=food_data.name,
        brand=food_data.brand,
        serving_size=food_data.serving_size,
        unit=food_data.unit,
        created_by_user_id=current_user.id,
        notes=food_data.notes,
    )
    db.add(food)
    await db.flush()
    
    # Add nutrients
    for nutrient_data in food_data.nutrients:
        food_nutrient = FoodNutrient(
            food_id=food.id,
            nutrient_id=nutrient_data.nutrient_id,
            amount_per_serving=nutrient_data.amount,
        )
        db.add(food_nutrient)
    
    await db.commit()
    await db.refresh(food)
    return food
```

### 2. Request Schema
**File:** `whati8/schemas/food.py`

```python
class FoodNutrientInput(BaseModel):
    nutrient_id: int
    amount: float

class FoodCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    brand: str | None = Field(None, max_length=100)
    serving_size: float = Field(..., gt=0)
    unit: str = Field(default="g", max_length=20)
    notes: str | None = Field(None, max_length=500)
    
    # Core nutrients (simplified - just the big 4)
    calories: float = Field(..., ge=0)
    protein: float = Field(default=0, ge=0)
    carbs: float = Field(default=0, ge=0)
    fat: float = Field(default=0, ge=0)
    fiber: float | None = Field(default=None, ge=0)
```

### 3. Nutrient ID Constants
Map common nutrients to their database IDs:
```python
# whati8/constants.py
NUTRIENT_IDS = {
    "calories": 1008,  # Energy (kcal)
    "protein": 1003,   # Protein
    "carbs": 1005,     # Carbohydrate, by difference
    "fat": 1004,       # Total lipid (fat)
    "fiber": 1079,     # Fiber, total dietary
}
```

## Frontend Implementation

### 1. Add Food Modal Component
**File:** `frontend/src/lib/components/AddFoodModal.svelte`

Form fields:
- Food name (required)
- Brand (optional)
- Serving size (required, default 1)
- Serving unit (dropdown: g, oz, ml, cup, piece, serving)
- Calories (required)
- Protein (optional, default 0)
- Carbs (optional, default 0)
- Fat (optional, default 0)
- Fiber (optional)
- Notes (optional)

### 2. Entry Points
Add "Create custom food" option:
- In `InlineAddFood.svelte` when no search results
- In `FoodSelector.svelte` dropdown ("Other..." → "Create new")
- Standalone page/route for bulk entry

### 3. UI Flow
1. User searches, no results found
2. Shows "Can't find it? Create a custom food" button
3. Opens AddFoodModal with search term pre-filled as name
4. User fills in nutrition info (from package label)
5. Saves → food available for logging
6. Returns to multi-food form with new food selected

## API Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/foods` | Create custom food |
| GET | `/foods/mine` | List user's custom foods |
| PUT | `/foods/{id}` | Update custom food (owner only) |
| DELETE | `/foods/{id}` | Delete custom food (owner only) |

## Testing Requirements

### Backend Tests
- Create food with all fields
- Create food with minimal fields (name, serving_size, calories)
- Reject invalid data (negative calories, empty name)
- Verify ownership (can't edit others' foods)
- Search includes custom foods
- Delete cascades properly

### Frontend Tests
- Form validation
- Successful creation flow
- Error handling
- Integration with multi-food form

## Implementation Order

1. **Backend schema** - FoodCreateRequest (30 min)
2. **Backend endpoint** - POST /foods (1 hour)
3. **Backend tests** (1 hour)
4. **Frontend modal** - AddFoodModal.svelte (2 hours)
5. **Integration** - Wire up to InlineAddFood/FoodSelector (1 hour)
6. **E2E testing** (1 hour)

**Estimated total: 6-7 hours**

## Future Enhancements

### Open Food Facts Integration
- Search OFF API when USDA has no results
- Import on-demand with proper attribution
- Barcode scanning support

### Community Features
- Share custom foods publicly (opt-in)
- Upvote/verify community foods
- Report incorrect nutrition data

### Import/Export
- CSV import for bulk custom foods
- Export user's custom foods
- Sync across devices
