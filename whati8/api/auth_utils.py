"""Authorization utilities for resource ownership checks."""

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.models.user import User


async def check_resource_owner(
    resource_user_id: int,
    current_user: User,
    resource_type: str = "resource",
) -> None:
    """
    Verify current user owns the resource.

    Args:
        resource_user_id: The user_id field from the resource
        current_user: The authenticated user making the request
        resource_type: Type of resource for error message (e.g., "food log")

    Raises:
        HTTPException: 404 if user doesn't own the resource (prevents enumeration)
    """
    if resource_user_id != current_user.id:
        # Return 404 instead of 403 to prevent resource enumeration
        raise HTTPException(
            status_code=404, detail=f"{resource_type.capitalize()} not found"
        )


async def get_user_resource_or_404(
    db: AsyncSession,
    model_class: type,
    resource_id: int,
    current_user: User,
    resource_type: str = "resource",
):
    """
    Get resource by ID and verify ownership.

    Args:
        db: Database session
        model_class: SQLAlchemy model class (e.g., FoodLog)
        resource_id: ID of the resource to fetch
        current_user: The authenticated user making the request
        resource_type: Type of resource for error message

    Returns:
        The resource if found and owned by current user

    Raises:
        HTTPException: 404 if resource not found or not owned by user
        ValueError: If model doesn't have user_id field

    Example:
        ```python
        @router.get("/logs/{log_id}")
        async def get_food_log(
            log_id: int,
            current_user: User = Depends(get_current_user),
            db: AsyncSession = Depends(get_db),
        ):
            from whati8.models.food_log import FoodLog
            log = await get_user_resource_or_404(
                db, FoodLog, log_id, current_user, "food log"
            )
            return log
        ```
    """
    resource = await db.get(model_class, resource_id)

    if not resource:
        raise HTTPException(
            status_code=404, detail=f"{resource_type.capitalize()} not found"
        )

    # Verify model has user_id field
    if not hasattr(resource, "user_id"):
        raise ValueError(
            f"{model_class.__name__} does not have user_id field. "
            "Cannot perform ownership check."
        )

    # Check ownership
    await check_resource_owner(resource.user_id, current_user, resource_type)

    return resource
