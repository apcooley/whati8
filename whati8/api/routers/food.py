"""
Food search and retrieval API endpoints.

Provides endpoints for searching foods (with fuzzy matching) and
retrieving detailed food information with nutrients.
"""

from anthropic import APIError as AnthropicAPIError
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from whati8.api.deps import get_current_user, get_db
from whati8.config import settings
from whati8.constants import (
    DEFAULT_PAGE_OFFSET,
    FOOD_SEARCH_DEFAULT_LIMIT,
    FOOD_SEARCH_MAX_LIMIT,
    FOOD_SEARCH_SIMILARITY_THRESHOLD,
    NUTRIENT_NAMES,
)
from whati8.models import Food, FoodNutrient, FoodPortion, Nutrient, User
from whati8.schemas.food import (
    FoodCreateRequest,
    FoodResponse,
    FoodSearchResponse,
    FoodSearchResultItem,
    PortionItem,
)
from whati8.schemas.food_resolver import FoodResolveRequest, FoodResolveResponse
from whati8.services.food_resolver import FoodResolverService

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/foods", tags=["foods"])


@router.post("/", response_model=FoodResponse)
async def create_food(
    food_data: FoodCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a custom food entry for the current user.

    Creates a new food item with nutrient information. Only the creating user
    can edit or delete this food.

    **Authentication required.**

    Example request:
    ```json
    {
        "name": "Vanilla Yogurt",
        "brand": "Brand Name",
        "serving_size": 150,
        "unit": "g",
        "calories": 95,
        "protein": 5,
        "carbs": 12,
        "fat": 0.5,
        "fiber": 0,
        "notes": "Plain yogurt"
    }
    ```

    Returns the created food with its nutrients.
    """
    # Create the food entry
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

    # Get or create nutrients and add them to the food
    nutrient_mapping = {
        "calories": (NUTRIENT_NAMES["calories"], food_data.calories),
        "protein": (NUTRIENT_NAMES["protein"], food_data.protein),
        "carbs": (NUTRIENT_NAMES["carbs"], food_data.carbs),
        "fat": (NUTRIENT_NAMES["fat"], food_data.fat),
    }

    # Add optional fiber if provided
    if food_data.fiber is not None:
        nutrient_mapping["fiber"] = (NUTRIENT_NAMES["fiber"], food_data.fiber)

    for nutrient_key, (nutrient_name, amount) in nutrient_mapping.items():
        # Look up nutrient by name
        nutrient = await db.scalar(
            select(Nutrient).where(Nutrient.name == nutrient_name)
        )

        if not nutrient:
            raise HTTPException(
                status_code=500,
                detail=f"Nutrient '{nutrient_name}' not found in database. Please contact support.",
            )

        # Add FoodNutrient entry
        food_nutrient = FoodNutrient(
            food_id=food.id,
            nutrient_id=nutrient.id,
            amount_per_serving=amount,
        )
        db.add(food_nutrient)

    await db.commit()
    
    # Reload the food with relationships eagerly loaded for serialization
    query = (
        select(Food)
        .options(selectinload(Food.food_nutrients).selectinload(FoodNutrient.nutrient))
        .where(Food.id == food.id)
    )
    result = await db.execute(query)
    food = result.scalar_one()

    return food


@router.get("/search", response_model=FoodSearchResponse)
async def search_foods(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(
        FOOD_SEARCH_DEFAULT_LIMIT,
        ge=1,
        le=FOOD_SEARCH_MAX_LIMIT,
        description="Results per page",
    ),
    offset: int = Query(
        DEFAULT_PAGE_OFFSET, ge=0, description="Result offset for pagination"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Search for foods using fuzzy text matching.

    Searches food names with typo-tolerance using PostgreSQL's pg_trgm extension.
    Returns foods ranked by similarity to search query.

    **Authentication required.**

    Examples:
    - `/foods/search?q=chicken` - Find all chicken-related foods
    - `/foods/search?q=chiken` - Typo-tolerant (will still find "chicken")
    - `/foods/search?q=brocoli&limit=10` - Limit results
    """
    # Use pg_trgm similarity search for fuzzy matching
    # similarity() returns a value between 0 and 1 (higher = better match)
    similarity_threshold = FOOD_SEARCH_SIMILARITY_THRESHOLD

    # Build query with similarity scoring and eager load nutrients + portions (prevents N+1)
    # Secondary sort by portion count (prefer foods with household portions)
    from whati8.models.food_portion import FoodPortion
    portion_count = (
        select(func.count(FoodPortion.id))
        .where(FoodPortion.food_id == Food.id)
        .correlate(Food)
        .scalar_subquery()
    )
    
    query = (
        select(
            Food,
            func.similarity(Food.name, q).label("similarity_score"),
        )
        .options(
            selectinload(Food.food_nutrients).selectinload(FoodNutrient.nutrient),
            selectinload(Food.portions),  # Load household portions
        )
        .where(func.similarity(Food.name, q) > similarity_threshold)
        .order_by(
            func.similarity(Food.name, q).desc(),
            portion_count.desc(),  # Prefer foods with portions
        )
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    # Count total results
    count_query = (
        select(func.count())
        .select_from(Food)
        .where(func.similarity(Food.name, q) > similarity_threshold)
    )
    total = await db.scalar(count_query) or 0

    # Build search result items using already-loaded relationships
    search_results = []
    for food, similarity_score in rows:
        # Extract key nutrients from already-loaded relationships (no more queries!)
        nutrients_map = {}
        for fn in food.food_nutrients:  # Already loaded via selectinload
            if fn.nutrient:  # Already loaded via selectinload
                nutrient_name = fn.nutrient.name
                # Map to result field names
                if "Calories" in nutrient_name or "Energy" in nutrient_name:
                    nutrients_map["calories"] = fn.amount_per_serving
                elif "Protein" in nutrient_name:
                    nutrients_map["protein"] = fn.amount_per_serving
                elif "Carbohydrate" in nutrient_name:
                    nutrients_map["carbs"] = fn.amount_per_serving
                elif "Fat" in nutrient_name or "lipid" in nutrient_name.lower():
                    nutrients_map["fat"] = fn.amount_per_serving

        # Build portion items from already-loaded portions
        portion_items = []
        for p in food.portions:
            unit_part = p.modifier if p.modifier else p.unit_name
            display_name = f"{float(p.amount)} {unit_part} ({float(p.gram_weight)}g)"
            portion_items.append(PortionItem(
                portion_id=p.id,
                amount=float(p.amount),
                unit_name=p.unit_name,
                modifier=p.modifier,
                gram_weight=float(p.gram_weight),
                display_name=display_name,
            ))

        result_item = FoodSearchResultItem(
            id=food.id,
            name=food.name,
            brand=food.brand,
            serving_size=food.serving_size,
            unit=food.unit,
            usda_fdc_id=food.usda_fdc_id,
            similarity=float(similarity_score),
            calories=nutrients_map.get("calories"),
            protein=nutrients_map.get("protein"),
            carbs=nutrients_map.get("carbs"),
            fat=nutrients_map.get("fat"),
            portions=portion_items,
        )
        search_results.append(result_item)

    return FoodSearchResponse(
        query=q,
        results=search_results,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/mine", response_model=list[FoodResponse])
async def list_user_foods(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all custom foods created by the current user.

    Returns all custom foods created by the authenticated user.

    **Authentication required.**
    """
    query = (
        select(Food)
        .options(selectinload(Food.food_nutrients).selectinload(FoodNutrient.nutrient))
        .where(Food.created_by_user_id == current_user.id)
        .order_by(Food.created_at.desc())
    )

    result = await db.execute(query)
    foods = result.scalars().all()

    return foods


@router.get("/{food_id}", response_model=FoodResponse)
async def get_food(
    food_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed food information with all nutrients.

    Returns complete food details including:
    - Food name, brand, serving size
    - All available nutrients with amounts
    - USDA FDC ID (if USDA food)

    **Authentication required.**
    """
    # Load food with all nutrients eagerly
    query = (
        select(Food)
        .options(selectinload(Food.food_nutrients).selectinload(FoodNutrient.nutrient))
        .where(Food.id == food_id)
    )

    result = await db.execute(query)
    food = result.scalar_one_or_none()

    if not food:
        raise HTTPException(status_code=404, detail="Food not found")

    return food


@router.put("/{food_id}", response_model=FoodResponse)
async def update_food(
    food_id: int,
    food_data: FoodCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a custom food entry.

    Only the user who created the food can update it.

    **Authentication required.**
    """
    # Fetch the food with eagerly loaded relationships
    query = (
        select(Food)
        .options(selectinload(Food.food_nutrients))
        .where(Food.id == food_id)
    )
    result = await db.execute(query)
    food = result.scalar_one_or_none()

    if not food:
        raise HTTPException(status_code=404, detail="Food not found")

    # Check ownership
    if food.created_by_user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only edit your own custom foods",
        )

    # Update basic fields
    food.name = food_data.name
    food.brand = food_data.brand
    food.serving_size = food_data.serving_size
    food.unit = food_data.unit
    food.notes = food_data.notes

    # Delete existing nutrients using delete statements instead of iterating
    # This avoids lazy-loading issues
    from sqlalchemy import delete
    await db.execute(delete(FoodNutrient).where(FoodNutrient.food_id == food_id))

    await db.flush()

    # Add updated nutrients
    nutrient_mapping = {
        "calories": (NUTRIENT_NAMES["calories"], food_data.calories),
        "protein": (NUTRIENT_NAMES["protein"], food_data.protein),
        "carbs": (NUTRIENT_NAMES["carbs"], food_data.carbs),
        "fat": (NUTRIENT_NAMES["fat"], food_data.fat),
    }

    if food_data.fiber is not None:
        nutrient_mapping["fiber"] = (NUTRIENT_NAMES["fiber"], food_data.fiber)

    for nutrient_key, (nutrient_name, amount) in nutrient_mapping.items():
        nutrient = await db.scalar(
            select(Nutrient).where(Nutrient.name == nutrient_name)
        )

        if not nutrient:
            raise HTTPException(
                status_code=500,
                detail=f"Nutrient '{nutrient_name}' not found in database.",
            )

        food_nutrient = FoodNutrient(
            food_id=food.id,
            nutrient_id=nutrient.id,
            amount_per_serving=amount,
        )
        db.add(food_nutrient)

    await db.commit()
    
    # Refresh the food to get the updated nutrients
    # Use joinedload for stronger relationship loading after commit
    refresh_query = (
        select(Food)
        .options(selectinload(Food.food_nutrients).joinedload(FoodNutrient.nutrient))
        .where(Food.id == food_id)
    )
    refresh_result = await db.execute(refresh_query)
    updated_food = refresh_result.scalar_one()

    return updated_food


@router.delete("/{food_id}")
async def delete_food(
    food_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a custom food entry.

    Only the user who created the food can delete it.

    **Authentication required.**
    """
    # Fetch the food
    food = await db.get(Food, food_id)

    if not food:
        raise HTTPException(status_code=404, detail="Food not found")

    # Check ownership
    if food.created_by_user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only delete your own custom foods",
        )

    await db.delete(food)
    await db.commit()

    return {"message": "Food deleted successfully"}


@router.post("/resolve", response_model=FoodResolveResponse)
@limiter.limit(f"{settings.rate_limit_ai_per_minute}/minute")
async def resolve_foods(
    request: Request,  # Starlette request for rate limiter
    body: FoodResolveRequest,  # Renamed from 'request' to avoid slowapi conflict
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Resolve natural language food description to structured data.

    Uses AI (Claude) to parse natural language input like "I had 2 eggs and toast"
    and matches parsed items against the food database. Returns structured data
    with multiple match options for user confirmation.

    **Authentication required.**

    **Requires ANTHROPIC_API_KEY in environment.**

    Example inputs:
    - "I had 2 eggs and toast for breakfast"
    - "8oz grilled chicken breast with broccoli"
    - "had some pasta and a salad for lunch"

    Returns:
    - Parsed food items (quantity, unit, confidence)
    - Database matches for each item (top N ranked by similarity)
    - Detected meal context (if mentioned)
    - Overall confidence score
    """
    try:
        response = await FoodResolverService.resolve_foods(
            db=db,
            text=body.text,
            meal_hint=body.meal_hint,
            max_matches_per_item=body.max_matches_per_item,
        )
        return response

    except ValueError as e:
        # Parsing errors (input too vague, no items extracted)
        raise HTTPException(status_code=400, detail=str(e))

    except AnthropicAPIError as e:
        # AI service errors
        if "authentication" in str(e).lower():
            raise HTTPException(
                status_code=500,
                detail="AI service authentication failed. Check server configuration.",
            )
        elif "rate_limit" in str(e).lower():
            raise HTTPException(
                status_code=429,
                detail="AI service rate limit exceeded. Please try again later.",
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"AI service error: {str(e)}",
            )
