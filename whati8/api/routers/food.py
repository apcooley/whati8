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
from sqlalchemy.orm import selectinload

from whati8.api.deps import get_current_user, get_db
from whati8.config import settings
from whati8.constants import (
    DEFAULT_PAGE_OFFSET,
    FOOD_SEARCH_DEFAULT_LIMIT,
    FOOD_SEARCH_MAX_LIMIT,
    FOOD_SEARCH_SIMILARITY_THRESHOLD,
)
from whati8.models import Food, FoodNutrient, User
from whati8.schemas.food import FoodResponse, FoodSearchResponse, FoodSearchResultItem
from whati8.schemas.food_resolver import FoodResolveRequest, FoodResolveResponse
from whati8.services.food_resolver import FoodResolverService

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/foods", tags=["foods"])


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

    # Build query with similarity scoring and eager load nutrients (prevents N+1)
    query = (
        select(
            Food,
            func.similarity(Food.name, q).label("similarity_score"),
        )
        .options(selectinload(Food.food_nutrients).selectinload(FoodNutrient.nutrient))
        .where(func.similarity(Food.name, q) > similarity_threshold)
        .order_by(func.similarity(Food.name, q).desc())
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
        )
        search_results.append(result_item)

    return FoodSearchResponse(
        query=q,
        results=search_results,
        total=total,
        limit=limit,
        offset=offset,
    )


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


@router.post("/resolve", response_model=FoodResolveResponse)
@limiter.limit(f"{settings.rate_limit_ai_per_minute}/minute")
async def resolve_foods(
    http_request: Request,
    request: FoodResolveRequest,
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
            text=request.text,
            meal_hint=request.meal_hint,
            max_matches_per_item=request.max_matches_per_item,
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
