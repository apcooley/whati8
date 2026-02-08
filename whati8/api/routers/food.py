"""
Food search and retrieval API endpoints.

Provides endpoints for searching foods (with fuzzy matching) and
retrieving detailed food information with nutrients.
"""

from anthropic import APIError as AnthropicAPIError
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from whati8.api.deps import get_current_user, get_db
from whati8.models import Food, FoodNutrient, Nutrient, User
from whati8.schemas.food import FoodResponse, FoodSearchResponse, FoodSearchResultItem
from whati8.schemas.food_resolver import FoodResolveRequest, FoodResolveResponse
from whati8.services.food_resolver import FoodResolverService

router = APIRouter(prefix="/foods", tags=["foods"])


@router.get("/search", response_model=FoodSearchResponse)
async def search_foods(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Result offset for pagination"),
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
    similarity_threshold = 0.1  # Lower threshold for broader matches

    # Build query with similarity scoring
    query = (
        select(
            Food,
            func.similarity(Food.name, q).label("similarity_score"),
        )
        .where(func.similarity(Food.name, q) > similarity_threshold)
        .order_by(func.similarity(Food.name, q).desc())
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    # Count total results
    count_query = select(func.count()).select_from(Food).where(
        func.similarity(Food.name, q) > similarity_threshold
    )
    total = await db.scalar(count_query) or 0

    # Get nutrient IDs for quick lookups
    nutrient_names = ["Calories", "Protein", "Total Carbohydrates", "Total Fat"]
    nutrient_result = await db.execute(
        select(Nutrient).where(Nutrient.name.in_(nutrient_names))
    )
    nutrient_map = {n.name: n.id for n in nutrient_result.scalars()}

    # Build search result items
    search_results = []
    for food, similarity_score in rows:
        # Get key nutrients for preview
        nutrient_query = select(FoodNutrient).where(
            FoodNutrient.food_id == food.id,
            FoodNutrient.nutrient_id.in_(nutrient_map.values()),
        )
        nutrients_result = await db.execute(nutrient_query)
        nutrients = {fn.nutrient_id: fn.amount_per_serving for fn in nutrients_result.scalars()}

        result_item = FoodSearchResultItem(
            id=food.id,
            name=food.name,
            brand=food.brand,
            serving_size=food.serving_size,
            unit=food.unit,
            usda_fdc_id=food.usda_fdc_id,
            similarity=float(similarity_score),
            calories=nutrients.get(nutrient_map.get("Calories")),
            protein=nutrients.get(nutrient_map.get("Protein")),
            carbs=nutrients.get(nutrient_map.get("Total Carbohydrates")),
            fat=nutrients.get(nutrient_map.get("Total Fat")),
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
        .options(
            selectinload(Food.food_nutrients).selectinload(FoodNutrient.nutrient)
        )
        .where(Food.id == food_id)
    )

    result = await db.execute(query)
    food = result.scalar_one_or_none()

    if not food:
        raise HTTPException(status_code=404, detail="Food not found")

    return food


@router.post("/resolve", response_model=FoodResolveResponse)
async def resolve_foods(
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
