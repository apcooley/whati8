"""
Profile foods API endpoints.

Provides endpoints for managing user's personal food library.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.api.deps import get_current_user, get_db
from whati8.constants import DEFAULT_PAGE_OFFSET
from whati8.models import User
from whati8.schemas.user_food import (
    UserFoodListResponse,
    UserFoodRegister,
    UserFoodResponse,
    UserFoodUpdate,
)
from whati8.services.user_food_service import UserFoodService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile/foods", tags=["profile"])


@router.post("/register", response_model=UserFoodResponse, status_code=status.HTTP_201_CREATED)
async def register_food(
    food_data: UserFoodRegister,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Register a food to user's profile.

    Adds a food from the database to the user's personal library with
    optional custom nickname, default quantity, and favorite status.

    **Authentication required.**

    Example:
    ```json
    {
        "food_id": 102,
        "nickname": "My eggs",
        "default_quantity": 2.0,
        "default_unit": "piece",
        "default_meal_id": 1,
        "is_favorite": true
    }
    ```
    """
    try:
        user_food = await UserFoodService.register_food(db, current_user.id, food_data)
        return user_food
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=UserFoodListResponse)
async def list_user_foods(
    q: str | None = Query(None, description="Search query (matches name or nickname)"),
    sort: str = Query(
        "recent",
        description="Sort order",
        pattern="^(recent|frequent|alpha|favorite)$",
    ),
    limit: int = Query(50, ge=1, le=100, description="Results per page"),
    offset: int = Query(DEFAULT_PAGE_OFFSET, ge=0, description="Pagination offset"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List user's profile foods with search and sorting.

    Sort options:
    - `recent`: Most recently used (default)
    - `frequent`: Most frequently used
    - `alpha`: Alphabetical by name
    - `favorite`: Favorites first, then recent

    **Authentication required.**
    """
    foods, total = await UserFoodService.get_user_foods(
        db, current_user.id, q=q, sort=sort, limit=limit, offset=offset
    )

    return UserFoodListResponse(
        foods=foods,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/recent", response_model=list[UserFoodResponse])
async def get_recent_foods(
    limit: int = Query(10, ge=1, le=50, description="Number of recent foods"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get most recently used foods.

    Returns up to `limit` foods sorted by last_used_at (most recent first).

    **Authentication required.**
    """
    foods = await UserFoodService.get_recent_foods(db, current_user.id, limit=limit)
    return foods


@router.get("/frequent", response_model=list[UserFoodResponse])
async def get_frequent_foods(
    limit: int = Query(10, ge=1, le=50, description="Number of frequent foods"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get most frequently used foods.

    Returns up to `limit` foods sorted by use_count (highest first).

    **Authentication required.**
    """
    foods = await UserFoodService.get_frequent_foods(db, current_user.id, limit=limit)
    return foods


@router.get("/search", response_model=list[UserFoodResponse])
async def search_profile_foods(
    q: str = Query("", description="Search query (partial name match)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Search user's registered foods for recipe ingredients.

    Searches all registered foods by name (case-insensitive partial match).
    Excludes expired recipe foods. Empty query returns recent foods.

    **Authentication required.**
    """
    foods = await UserFoodService.search_profile_foods(
        db, current_user.id, q=q, limit=limit
    )
    return foods


@router.put("/{user_food_id}", response_model=UserFoodResponse)
async def update_user_food(
    user_food_id: int,
    update_data: UserFoodUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update user food settings.

    Modify nickname, defaults, or favorite status. All fields optional.

    **Authentication required. Users can only update their own foods.**
    """
    try:
        user_food = await UserFoodService.update_user_food(
            db, current_user.id, user_food_id, update_data
        )
        return user_food
    except ValueError:
        raise HTTPException(status_code=404, detail="Resource not found")


@router.delete("/{user_food_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_food(
    user_food_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Remove food from user's profile.

    Does not delete the food from the database, only removes it from
    user's personal library. Food logs remain intact.

    **Authentication required. Users can only delete their own foods.**
    """
    try:
        await UserFoodService.delete_user_food(db, current_user.id, user_food_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Resource not found")
