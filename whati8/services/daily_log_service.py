"""Service layer for daily log views and quick logging."""

from datetime import datetime, date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from whati8.logging_config import get_logger
from whati8.models import Food, FoodLog, FoodNutrient, Meal, UserFood, UserGoal
from whati8.schemas.daily_log import QuickLogCreate
from whati8.services.nutrient_calculator import NutrientCalculator, NutrientInput

logger = get_logger(__name__)


def _portion_scale(log, food):
    """Calculate scale factor for nutrient values.

    USDA foods: amount_per_serving is per 100g.
    Custom foods (created_by_user_id set): amount_per_serving is per serving_size.

    Returns multiplier so: amount_per_serving * scale = actual nutrient amount.
    """
    import re
    from decimal import Decimal

    is_custom = bool(getattr(food, 'created_by_user_id', None))
    base = food.serving_size if is_custom and food.serving_size else Decimal(100)

    if not log.unit or not hasattr(food, 'portions'):
        return log.quantity

    # If unit is "grams" or "g", quantity IS the gram weight
    if log.unit.lower() in ("grams", "g"):
        return log.quantity / base

    # If unit matches the food's native unit (e.g. "oz" for custom food with unit="oz")
    if is_custom and log.unit.lower() == (food.unit or '').lower():
        return log.quantity  # 1 unit = 1 serving

    # Try to find matching portion from USDA portions
    for p in food.portions:
        desc = p.portion_description or p.modifier or p.unit_name or ""
        clean_desc = re.sub(r"^[\d.]+ undetermined ", "", desc)
        norm = lambda s: re.sub(r'(\d+)\.0g\)', lambda m: m.group(1) + 'g)', s)  # noqa: E731
        if norm(clean_desc) == norm(log.unit):
            return log.quantity * p.gram_weight / base

    return log.quantity


async def compute_food_summary(
    db: AsyncSession, user_id: int, food: Food, quantity_grams: float
) -> list[dict]:
    """Compute summary nutrients for a food at a given gram quantity.

    Uses the same user config, coalesce strategies, and formula engine
    as the daily log view. Returns the same format as per-log summary_nutrients.

    This is the single source of truth for nutrient display anywhere in the app.
    """
    from whati8.api.routers.summary_config import _ensure_defaults

    config_items = await _ensure_defaults(db, user_id)
    item = NutrientInput(food=food, quantity=quantity_grams, unit="grams")
    return NutrientCalculator.compute_summary([item], config_items, formula_mode="per_item")


class DailyLogService:
    """Service for daily log views and quick logging from profile."""

    @staticmethod
    async def quick_log_food(
        db: AsyncSession, user_id: int, data: QuickLogCreate
    ) -> FoodLog:
        """
        Create a food log from user's profile food with defaults.

        Raises:
            ValueError: If user_food not found, access denied, or missing defaults
        """
        # Get user food with eager loading
        result = await db.execute(
            select(UserFood)
            .where(UserFood.id == data.user_food_id, UserFood.user_id == user_id)
            .options(selectinload(UserFood.food))
        )
        user_food = result.scalar_one_or_none()

        if not user_food:
            raise ValueError("User food not found or access denied")

        # Determine quantity and unit
        quantity = data.quantity if data.quantity is not None else user_food.default_quantity
        unit = data.unit if data.unit is not None else user_food.default_unit
        meal_id = data.meal_id if data.meal_id is not None else user_food.default_meal_id
        logged_at = data.logged_at if data.logged_at is not None else datetime.now()

        if quantity is None:
            raise ValueError("Quantity is required (no default set)")
        if unit is None:
            raise ValueError("Unit is required (no default set)")

        # Create food log
        food_log = FoodLog(
            user_id=user_id,
            food_id=user_food.food_id,
            user_food_id=user_food.id,
            meal_id=meal_id,
            quantity=quantity,
            unit=unit,
            logged_at=logged_at,
        )
        db.add(food_log)

        # Increment use count
        user_food.use_count += 1
        user_food.last_used_at = datetime.now()

        await db.commit()
        await db.refresh(food_log)

        # Load relationships for response
        result = await db.execute(
            select(FoodLog)
            .options(
                selectinload(FoodLog.food).selectinload(Food.food_nutrients).selectinload(FoodNutrient.nutrient),
                selectinload(FoodLog.food).selectinload(Food.portions),
                selectinload(FoodLog.meal),
            )
            .where(FoodLog.id == food_log.id)
        )
        food_log = result.scalar_one()

        logger.info(
            f"User {user_id} quick-logged {user_food.food.name} via user_food {user_food.id}"
        )
        return food_log

    @staticmethod
    async def get_daily_logs(
        db: AsyncSession, user_id: int, target_date: date
    ) -> dict:
        """
        Get all logs for a specific date, grouped by meal with nutrient summary.

        Returns:
            Dict with structure:
            {
                "date": "2026-03-02",
                "meals": [
                    {
                        "meal": {"id": 1, "name": "Breakfast", "display_order": 1},
                        "logs": [
                            {
                                "id": 501,
                                "food_id": 102,
                                "food_name": "Egg, whole, raw",
                                "quantity": 2.0,
                                "unit": "piece",
                                "logged_at": "2026-03-02T08:30:00Z",
                                "calories": 144,
                                "protein": 12.6,
                                ...
                            }
                        ]
                    }
                ],
                "summary": {
                    "nutrients": [
                        {"nutrient_id": 1, "name": "Calories", "value": 1850, "target": 2000, "unit": "kcal"}
                    ]
                }
            }
        """
        # Get all logs for the date
        start_of_day = datetime.combine(target_date, datetime.min.time())
        end_of_day = datetime.combine(target_date, datetime.max.time())

        result = await db.execute(
            select(FoodLog)
            .where(
                FoodLog.user_id == user_id,
                FoodLog.logged_at >= start_of_day,
                FoodLog.logged_at <= end_of_day,
            )
            .options(
                selectinload(FoodLog.food).selectinload(Food.food_nutrients).selectinload(FoodNutrient.nutrient),
                selectinload(FoodLog.food).selectinload(Food.portions),
                selectinload(FoodLog.meal),
            )
            .order_by(FoodLog.logged_at)
        )
        logs = list(result.scalars().all())

        # Get all meals for grouping
        meals_result = await db.execute(
            select(Meal).order_by(Meal.display_order)
        )
        all_meals = list(meals_result.scalars().all())

        # Load user summary config early (needed for per-log summary)
        from whati8.api.routers.summary_config import _ensure_defaults
        config_items = await _ensure_defaults(db, user_id)

        def _format_log(log) -> dict:
            """Format a single log entry using NutrientCalculator for all nutrient fields."""
            item = NutrientInput(food=log.food, quantity=float(log.quantity), unit=log.unit or "grams")
            # Compute nutrients once, use for both convenience fields and summary
            from whati8.services.nutrient_calculator import compute_item_nutrients
            friendly, by_id = compute_item_nutrients(item)
            log_summary = NutrientCalculator.compute_summary_from_precomputed(
                [friendly], [by_id], config_items, formula_mode="per_item"
            )

            return {
                "id": log.id,
                "food_id": log.food_id,
                "food_name": log.food.name,
                "quantity": float(log.quantity),
                "unit": log.unit or log.food.unit,
                "logged_at": log.logged_at,
                "calories": round(friendly.get("calories", 0), 1),
                "protein": round(friendly.get("protein", 0), 1),
                "carbs": round(friendly.get("carbs", 0), 1),
                "fat": round(friendly.get("fat", 0), 1),
                "fiber": round(friendly.get("fiber", 0), 1),
                "summary_nutrients": log_summary,
            }

        # Group logs by meal
        meal_groups = []
        for meal in all_meals:
            meal_logs = [log for log in logs if log.meal_id == meal.id]
            if meal_logs:
                meal_groups.append({
                    "meal": {
                        "id": meal.id,
                        "name": meal.name,
                        "display_order": meal.display_order,
                    },
                    "logs": [_format_log(log) for log in meal_logs],
                })

        # Add ungrouped logs (null meal_id)
        ungrouped_logs = [log for log in logs if log.meal_id is None]
        if ungrouped_logs:
            meal_groups.append({
                "meal": {
                    "id": 0,
                    "name": "Other",
                    "display_order": 999,
                },
                "logs": [_format_log(log) for log in ungrouped_logs],
            })

        # Calculate daily nutrient totals using NutrientCalculator
        all_items = [
            NutrientInput(food=log.food, quantity=float(log.quantity), unit=log.unit or "grams")
            for log in logs
        ]
        nc_results = NutrientCalculator.compute_summary(all_items, config_items, formula_mode="per_item")

        # Build summary_nutrients in expected response format (with nutrient_id and target)
        summary_nutrients = []
        for cfg, result_item in zip(config_items, nc_results):
            summary_nutrients.append({
                "nutrient_id": cfg.nutrient_id or 0,
                "name": result_item["name"],
                "unit": result_item["unit"],
                "value": round(result_item["value"], 1),
                "target": None,
            })

        # Get user goals (for targets)
        goals_result = await db.execute(
            select(UserGoal)
            .where(UserGoal.user_id == user_id)
        )
        goals = list(goals_result.scalars().all())
        for goal in goals:
            for nutrient in summary_nutrients:
                if nutrient["name"].lower() == goal.goal_type.lower():
                    nutrient["target"] = float(goal.target_value)

        return {
            "date": target_date.isoformat(),
            "meals": meal_groups,
            "summary": {
                "nutrients": summary_nutrients,
            },
        }
