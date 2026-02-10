"""
Food logging CRUD API endpoints.

Provides endpoints for tracking daily food consumption with full CRUD operations.
"""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from whati8.api.auth_utils import get_user_resource_or_404
from whati8.api.deps import get_current_user, get_db
from whati8.constants import (
    DEFAULT_PAGE_OFFSET,
    FOOD_LOG_DEFAULT_LIMIT,
    FOOD_LOG_MAX_LIMIT,
)
from whati8.models import Food, FoodLog, FoodNutrient, Meal, User
from whati8.schemas.food_log import (
    FoodLogCreate,
    FoodLogListResponse,
    FoodLogResponse,
    FoodLogUpdate,
)
from whati8.schemas.multi_food import FoodLogBatchRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/logs", tags=["food-logs"])


@router.post("", response_model=FoodLogResponse, status_code=status.HTTP_201_CREATED)
async def create_food_log(
    log_data: FoodLogCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new food log entry.

    Records food consumption with quantity, timestamp, and optional meal category.
    Validates that the food and meal (if provided) exist in the database.

    **Authentication required.**

    Example:
    ```json
    {
        "food_id": 102,
        "meal_id": 1,
        "quantity": 1.5,
        "logged_at": "2026-02-07T08:30:00",
        "notes": "Breakfast broccoli"
    }
    ```
    """
    # Validate food exists
    food = await db.get(Food, log_data.food_id)
    if not food:
        raise HTTPException(
            status_code=404,
            detail=f"Food with id {log_data.food_id} not found",
        )

    # Validate meal exists (if provided)
    if log_data.meal_id is not None:
        meal = await db.get(Meal, log_data.meal_id)
        if not meal:
            raise HTTPException(
                status_code=404,
                detail=f"Meal with id {log_data.meal_id} not found",
            )

    # Create food log
    food_log = FoodLog(
        user_id=current_user.id,
        food_id=log_data.food_id,
        meal_id=log_data.meal_id,
        quantity=log_data.quantity,
        logged_at=log_data.logged_at,
        notes=log_data.notes,
    )

    db.add(food_log)
    await db.commit()
    await db.refresh(food_log)

    # Load relationships for response
    await db.refresh(
        food_log,
        [
            "food",
            "meal",
        ],
    )

    # Eager load food nutrients
    query = (
        select(FoodLog)
        .options(
            selectinload(FoodLog.food)
            .selectinload(Food.food_nutrients)
            .selectinload(FoodNutrient.nutrient),
            selectinload(FoodLog.meal),
        )
        .where(FoodLog.id == food_log.id)
    )
    result = await db.execute(query)
    food_log = result.scalar_one()

    return food_log


@router.get("", response_model=FoodLogListResponse)
async def list_food_logs(
    date_filter: str | None = Query(
        None,
        alias="date",
        description="Filter by date (YYYY-MM-DD)",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    ),
    meal_id: int | None = Query(None, description="Filter by meal category"),
    limit: int = Query(
        FOOD_LOG_DEFAULT_LIMIT,
        ge=1,
        le=FOOD_LOG_MAX_LIMIT,
        description="Results per page",
    ),
    offset: int = Query(
        DEFAULT_PAGE_OFFSET, ge=0, description="Result offset for pagination"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List food logs for the authenticated user.

    Supports filtering by date and meal category. Results are ordered by
    logged_at timestamp (most recent first) and include full food details
    with nutrients for easy dashboard/summary views.

    **Authentication required.**

    Examples:
    - `/logs` - All logs for current user
    - `/logs?date=2026-02-07` - All logs for specific date
    - `/logs?meal_id=1` - All breakfast logs
    - `/logs?date=2026-02-07&meal_id=1` - Breakfast logs for specific date
    """
    # Build query with filters
    query = select(FoodLog).where(FoodLog.user_id == current_user.id)

    # Filter by date if provided
    if date_filter:
        try:
            filter_date = date.fromisoformat(date_filter)
            query = query.where(func.date(FoodLog.logged_at) == filter_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date format: {date_filter}. Use YYYY-MM-DD.",
            )

    # Filter by meal if provided
    if meal_id is not None:
        query = query.where(FoodLog.meal_id == meal_id)

    # Eager load relationships to avoid N+1 queries
    query = query.options(
        selectinload(FoodLog.food)
        .selectinload(Food.food_nutrients)
        .selectinload(FoodNutrient.nutrient),
        selectinload(FoodLog.meal),
    )

    # Order by most recent first
    query = query.order_by(FoodLog.logged_at.desc())

    # Apply pagination
    query = query.offset(offset).limit(limit)

    # Execute query
    result = await db.execute(query)
    logs = result.scalars().all()

    # Count total results
    count_query = select(func.count()).select_from(FoodLog).where(
        FoodLog.user_id == current_user.id
    )
    if date_filter:
        filter_date = date.fromisoformat(date_filter)
        count_query = count_query.where(func.date(FoodLog.logged_at) == filter_date)
    if meal_id is not None:
        count_query = count_query.where(FoodLog.meal_id == meal_id)

    total = await db.scalar(count_query) or 0

    return FoodLogListResponse(
        logs=list(logs),
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{log_id}", response_model=FoodLogResponse)
async def get_food_log(
    log_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific food log entry.

    Returns full food log details including complete food information
    with all nutrients and meal category.

    **Authentication required.** Only returns logs owned by the current user.
    """
    # First fetch with basic get to check ownership
    log = await get_user_resource_or_404(
        db, FoodLog, log_id, current_user, "food log"
    )

    # Now reload with eager loading for full details
    query = (
        select(FoodLog)
        .options(
            selectinload(FoodLog.food)
            .selectinload(Food.food_nutrients)
            .selectinload(FoodNutrient.nutrient),
            selectinload(FoodLog.meal),
        )
        .where(FoodLog.id == log_id)
    )
    result = await db.execute(query)
    log = result.scalar_one()

    return log


@router.put("/{log_id}", response_model=FoodLogResponse)
async def update_food_log(
    log_id: int,
    log_data: FoodLogUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a food log entry.

    All fields are optional - only provided fields will be updated.
    Validates that new food_id and meal_id (if changed) exist in database.

    **Authentication required.** Only allows updating logs owned by current user.

    Example:
    ```json
    {
        "quantity": 2.0,
        "notes": "Updated quantity"
    }
    ```
    """
    # Fetch and verify ownership
    log = await get_user_resource_or_404(
        db, FoodLog, log_id, current_user, "food log"
    )

    # Validate food_id if being changed
    if log_data.food_id is not None and log_data.food_id != log.food_id:
        food = await db.get(Food, log_data.food_id)
        if not food:
            raise HTTPException(
                status_code=404,
                detail=f"Food with id {log_data.food_id} not found",
            )
        log.food_id = log_data.food_id

    # Validate meal_id if being changed
    if log_data.meal_id is not None and log_data.meal_id != log.meal_id:
        meal = await db.get(Meal, log_data.meal_id)
        if not meal:
            raise HTTPException(
                status_code=404,
                detail=f"Meal with id {log_data.meal_id} not found",
            )
        log.meal_id = log_data.meal_id

    # Update other fields if provided
    if log_data.quantity is not None:
        log.quantity = log_data.quantity
    if log_data.logged_at is not None:
        log.logged_at = log_data.logged_at
    if log_data.notes is not None:
        log.notes = log_data.notes

    await db.commit()
    await db.refresh(log)

    # Reload with eager loading for full details
    query = (
        select(FoodLog)
        .options(
            selectinload(FoodLog.food)
            .selectinload(Food.food_nutrients)
            .selectinload(FoodNutrient.nutrient),
            selectinload(FoodLog.meal),
        )
        .where(FoodLog.id == log_id)
    )
    result = await db.execute(query)
    log = result.scalar_one()

    return log


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_food_log(
    log_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a food log entry.

    **Authentication required.** Only allows deleting logs owned by current user.

    Returns 204 No Content on success.
    """
    # Fetch and verify ownership
    log = await get_user_resource_or_404(
        db, FoodLog, log_id, current_user, "food log"
    )

    await db.delete(log)
    await db.commit()

    return None


@router.post("/batch", response_model=dict)
async def create_logs_batch(
    request: FoodLogBatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Batch create food logs. All-or-nothing transaction.

    Creates multiple food log entries in a single atomic transaction.
    If any entry fails validation, the entire batch is rolled back.

    **Authentication required.**

    Example:
    ```json
    {
        "entries": [
            {"food_id": 102, "quantity": 150.0, "meal_id": 1},
            {"food_id": 234, "quantity": 200.0, "meal_id": 1}
        ],
        "logged_at": "2026-02-09T08:30:00"
    }
    ```
    """
    from datetime import datetime

    try:
        # Parse logged_at timestamp or use current time
        if request.logged_at:
            logged_at_str = request.logged_at.replace("Z", "+00:00")
            logged_at = datetime.fromisoformat(logged_at_str)
            # Convert to naive datetime (remove timezone info)
            if logged_at.tzinfo is not None:
                logged_at = logged_at.replace(tzinfo=None)
        else:
            logged_at = datetime.utcnow()

        # Validate all food_ids exist
        food_ids = [entry.food_id for entry in request.entries]
        result = await db.execute(
            select(Food.id).where(Food.id.in_(food_ids))
        )
        existing_food_ids = set(result.scalars().all())

        missing_food_ids = set(food_ids) - existing_food_ids
        if missing_food_ids:
            raise HTTPException(
                status_code=404,
                detail=f"Foods not found: {sorted(missing_food_ids)}",
            )

        # Create all food logs in transaction
        created_logs = []
        for entry in request.entries:
            food_log = FoodLog(
                user_id=current_user.id,
                food_id=entry.food_id,
                meal_id=entry.meal_id,
                quantity=entry.quantity,
                logged_at=logged_at,
            )
            db.add(food_log)
            created_logs.append(food_log)

        # Commit transaction
        await db.commit()

        return {
            "logged": len(created_logs),
            "message": f"Successfully logged {len(created_logs)} food(s)",
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Rollback on any error
        await db.rollback()
        logger.error(f"Error creating batch logs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create batch logs: {str(e)}",
        )
