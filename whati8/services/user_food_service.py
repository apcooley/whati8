"""Service layer for user food profile management."""

from datetime import datetime, timezone

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from whati8.logging_config import get_logger
from whati8.models import Food, FoodNutrient, UserFood
from whati8.schemas.user_food import UserFoodRegister, UserFoodUpdate

logger = get_logger(__name__)


class UserFoodService:
    """Service for managing user's personal food library."""

    @staticmethod
    async def register_food(
        db: AsyncSession, user_id: int, data: UserFoodRegister
    ) -> UserFood:
        """
        Register a food to user's profile.

        Raises:
            ValueError: If food doesn't exist or is already registered
        """
        # Check if food exists
        food = await db.scalar(select(Food).where(Food.id == data.food_id))
        if not food:
            raise ValueError(f"Food with ID {data.food_id} not found")

        # Check if already registered
        existing = await db.scalar(
            select(UserFood).where(
                UserFood.user_id == user_id, UserFood.food_id == data.food_id
            )
        )
        if existing:
            raise ValueError(f"Food {food.name} is already in your profile")

        # Create user food entry
        user_food = UserFood(
            user_id=user_id,
            food_id=data.food_id,
            nickname=data.nickname,
            default_quantity=data.default_quantity,
            default_unit=data.default_unit,
            default_meal_id=data.default_meal_id,
            is_favorite=data.is_favorite,
        )
        db.add(user_food)
        await db.commit()
        await db.refresh(user_food)

        # Eager load relationships
        result = await db.execute(
            select(UserFood)
            .options(
                selectinload(UserFood.food).selectinload(Food.food_nutrients).selectinload(FoodNutrient.nutrient),
                selectinload(UserFood.food).selectinload(Food.portions),
                selectinload(UserFood.default_meal),
            )
            .where(UserFood.id == user_food.id)
        )
        user_food = result.scalar_one()

        logger.info(
            f"User {user_id} registered food {food.name} (ID: {user_food.id})"
        )
        return user_food

    @staticmethod
    async def get_user_foods(
        db: AsyncSession,
        user_id: int,
        q: str | None = None,
        sort: str = "recent",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[UserFood], int]:
        """
        List user's profile foods with search and sorting.

        Args:
            q: Search query (matches name or nickname)
            sort: Sort order (recent, frequent, alpha, favorite)
            limit: Results per page
            offset: Pagination offset

        Returns:
            Tuple of (foods, total_count)
        """
        # Build base query
        query = select(UserFood).where(UserFood.user_id == user_id)

        # Apply search filter
        if q:
            query = query.join(Food, UserFood.food_id == Food.id).where(
                or_(
                    func.lower(Food.name).contains(func.lower(q)),
                    func.lower(UserFood.nickname).contains(func.lower(q)),
                )
            )

        # Apply sorting
        if sort == "recent":
            query = query.order_by(desc(UserFood.last_used_at))
        elif sort == "frequent":
            query = query.order_by(desc(UserFood.use_count))
        elif sort == "alpha":
            query = query.join(Food, UserFood.food_id == Food.id).order_by(Food.name)
        elif sort == "favorite":
            query = query.order_by(desc(UserFood.is_favorite), desc(UserFood.last_used_at))

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query)

        # Apply pagination and eager loading
        query = (
            query.options(
                selectinload(UserFood.food).selectinload(Food.food_nutrients).selectinload(FoodNutrient.nutrient),
                selectinload(UserFood.food).selectinload(Food.portions),
                selectinload(UserFood.default_meal),
            )
            .limit(limit)
            .offset(offset)
        )

        result = await db.execute(query)
        foods = list(result.scalars().all())

        return foods, total or 0

    @staticmethod
    async def get_recent_foods(
        db: AsyncSession, user_id: int, limit: int = 10
    ) -> list[UserFood]:
        """Get most recently used foods."""
        from sqlalchemy.sql.functions import coalesce
        result = await db.execute(
            select(UserFood)
            .where(UserFood.user_id == user_id)
            .options(
                selectinload(UserFood.food).selectinload(Food.food_nutrients).selectinload(FoodNutrient.nutrient),
                selectinload(UserFood.food).selectinload(Food.portions),
                selectinload(UserFood.default_meal),
            )
            .order_by(
                coalesce(UserFood.last_used_at, UserFood.created_at).desc()
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_frequent_foods(
        db: AsyncSession, user_id: int, limit: int = 10
    ) -> list[UserFood]:
        """Get most frequently used foods."""
        result = await db.execute(
            select(UserFood)
            .where(UserFood.user_id == user_id, UserFood.use_count > 0)
            .options(
                selectinload(UserFood.food).selectinload(Food.food_nutrients).selectinload(FoodNutrient.nutrient),
                selectinload(UserFood.food).selectinload(Food.portions),
                selectinload(UserFood.default_meal),
            )
            .order_by(desc(UserFood.use_count))
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_user_food(
        db: AsyncSession, user_id: int, user_food_id: int
    ) -> UserFood | None:
        """Get a single user food by ID with ownership check."""
        result = await db.execute(
            select(UserFood)
            .where(UserFood.id == user_food_id, UserFood.user_id == user_id)
            .options(
                selectinload(UserFood.food).selectinload(Food.food_nutrients).selectinload(FoodNutrient.nutrient),
                selectinload(UserFood.food).selectinload(Food.portions),
                selectinload(UserFood.default_meal),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_user_food(
        db: AsyncSession, user_id: int, user_food_id: int, data: UserFoodUpdate
    ) -> UserFood:
        """
        Update user food settings.

        Raises:
            ValueError: If user food not found or access denied
        """
        user_food = await UserFoodService.get_user_food(db, user_id, user_food_id)
        if not user_food:
            raise ValueError("User food not found or access denied")

        # Update fields if provided
        if data.nickname is not None:
            user_food.nickname = data.nickname
        if data.default_quantity is not None:
            user_food.default_quantity = data.default_quantity
        if data.default_unit is not None:
            user_food.default_unit = data.default_unit
        if data.default_meal_id is not None:
            user_food.default_meal_id = data.default_meal_id
        if data.is_favorite is not None:
            user_food.is_favorite = data.is_favorite

        await db.commit()
        await db.refresh(user_food)

        logger.info(f"User {user_id} updated user_food {user_food_id}")
        return user_food

    @staticmethod
    async def delete_user_food(
        db: AsyncSession, user_id: int, user_food_id: int
    ) -> None:
        """
        Remove food from user's profile.

        Raises:
            ValueError: If user food not found or access denied
        """
        user_food = await db.scalar(
            select(UserFood).where(
                UserFood.id == user_food_id, UserFood.user_id == user_id
            )
        )
        if not user_food:
            raise ValueError("User food not found or access denied")

        await db.delete(user_food)
        await db.commit()

        logger.info(f"User {user_id} removed user_food {user_food_id}")

    @staticmethod
    async def increment_use_count(
        db: AsyncSession, user_food_id: int
    ) -> None:
        """
        Increment use_count and update last_used_at for a user food.
        Called when logging from profile.
        """
        user_food = await db.scalar(
            select(UserFood).where(UserFood.id == user_food_id)
        )
        if user_food:
            user_food.use_count += 1
            user_food.last_used_at = datetime.now(timezone.utc)
            await db.commit()

    @staticmethod
    async def search_profile_foods(
        db: AsyncSession,
        user_id: int,
        q: str = "",
        limit: int = 20,
    ) -> list[UserFood]:
        """
        Search user's registered foods for recipe ingredients.

        Prioritizes user's registered foods over USDA search.
        Excludes expired recipe foods.

        Args:
            q: Search query (case-insensitive partial match on food name)
            limit: Maximum results to return

        Returns:
            List of UserFood objects ordered by last_used_at DESC
        """
        from sqlalchemy.sql.functions import coalesce

        # Build query
        query = (
            select(UserFood)
            .join(Food, UserFood.food_id == Food.id)
            .where(
                UserFood.user_id == user_id,
                Food.is_recipe_expired != True,  # Exclude expired recipes
            )
        )

        # Apply search filter if provided
        if q.strip():
            query = query.where(func.lower(Food.name).contains(func.lower(q)))

        # Order by last_used_at (most recent first), falling back to created_at
        query = query.order_by(
            coalesce(UserFood.last_used_at, UserFood.created_at).desc()
        )

        # Apply limit
        query = query.limit(limit)

        # Eager load relationships
        query = query.options(
            selectinload(UserFood.food).selectinload(Food.food_nutrients).selectinload(FoodNutrient.nutrient),
            selectinload(UserFood.food).selectinload(Food.portions),
            selectinload(UserFood.default_meal),
        )

        result = await db.execute(query)
        return list(result.scalars().all())
