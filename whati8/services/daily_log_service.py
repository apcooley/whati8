"""Service layer for daily log views and quick logging."""

from datetime import datetime, date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from whati8.logging_config import get_logger
from whati8.models import Food, FoodLog, FoodNutrient, Meal, UserFood, UserGoal
from whati8.schemas.daily_log import QuickLogCreate

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
        norm = lambda s: re.sub(r'(\d+)\.0g\)', lambda m: m.group(1) + 'g)', s)
        if norm(clean_desc) == norm(log.unit):
            return log.quantity * p.gram_weight / base
    
    return log.quantity


# Energy nutrient IDs that should all be treated as "Calories"
ENERGY_NUTRIENT_IDS = {39, 199, 200}

# Carbohydrate nutrient IDs
CARB_NUTRIENT_IDS = {81, 107}  # by difference, by summation


def _coalesce_energy(food_nutrients, portion_scale_factor) -> float | None:
    """Apply energy coalesce: Atwater General (199) > Atwater Specific (200) > Plain Energy (39).
    
    Also matches by name for environments where IDs differ (e.g., test databases).
    """
    energy_values = {}
    generic_energy_value = None
    
    for fn in food_nutrients:
        scaled_value = float(fn.amount_per_serving * portion_scale_factor)
        
        # Match by ID (production database)
        if fn.nutrient_id in ENERGY_NUTRIENT_IDS:
            energy_values[fn.nutrient_id] = scaled_value
        # Match by name (test databases or other schemas)
        elif fn.nutrient.name.lower().startswith("energy"):
            # Distinguish between specific Atwater factors and generic Energy
            name_lower = fn.nutrient.name.lower()
            if "atwater general" in name_lower:
                energy_values[199] = scaled_value
            elif "atwater specific" in name_lower:
                energy_values[200] = scaled_value
            else:
                # Generic "Energy" - use as fallback
                generic_energy_value = scaled_value
    
    # Priority: Atwater General (199) > Atwater Specific (200) > Plain Energy (39) > Generic Energy by name
    if 199 in energy_values:
        return energy_values[199]
    elif 200 in energy_values:
        return energy_values[200]
    elif 39 in energy_values:
        return energy_values[39]
    elif generic_energy_value is not None:
        return generic_energy_value
    return None


def _coalesce_carbs(food_nutrients, portion_scale_factor) -> float | None:
    """Apply carbs coalesce: by_summation (107) > MAX(by_difference (81), 0).
    
    Also matches by name for environments where IDs differ (e.g., test databases).
    """
    carb_values = {}
    generic_carb_value = None
    
    for fn in food_nutrients:
        scaled_value = float(fn.amount_per_serving * portion_scale_factor)
        
        # Match by ID (production database)
        if fn.nutrient_id in CARB_NUTRIENT_IDS:
            carb_values[fn.nutrient_id] = scaled_value
        # Match by name (test databases or other schemas)
        elif "carbohydrate" in fn.nutrient.name.lower():
            name_lower = fn.nutrient.name.lower()
            if "summation" in name_lower:
                carb_values[107] = scaled_value
            elif "difference" in name_lower:
                carb_values[81] = scaled_value
            else:
                # Generic "Carbohydrate" - use as fallback
                generic_carb_value = scaled_value
    
    # Priority: summation (107) > clamped difference (81) > generic carbohydrate by name
    if 107 in carb_values:
        return carb_values[107]
    elif 81 in carb_values:
        return max(carb_values[81], 0)  # Clamp negative to 0
    elif generic_carb_value is not None:
        return max(generic_carb_value, 0)  # Clamp negative to 0
    return None


async def compute_food_summary(
    db: AsyncSession, user_id: int, food: Food, quantity_grams: float
) -> list[dict]:
    """Compute summary nutrients for a food at a given gram quantity.

    Uses the same user config, coalesce strategies, and formula engine
    as the daily log view. Returns the same format as per-log summary_nutrients.

    This is the single source of truth for nutrient display anywhere in the app.
    """
    from whati8.api.routers.summary_config import _ensure_defaults
    from whati8.services.formula_engine import evaluate_formula

    config_items = await _ensure_defaults(db, user_id)
    if not config_items:
        return []

    # Scale factor: quantity_grams / base
    from decimal import Decimal
    is_custom = bool(getattr(food, 'created_by_user_id', None))
    base = float(food.serving_size) if is_custom and food.serving_size else 100.0
    scale = quantity_grams / base if base > 0 else 0

    # Extract core nutrients using coalesce strategies
    calories = _coalesce_energy(food.food_nutrients, Decimal(str(scale)))
    carbs = _coalesce_carbs(food.food_nutrients, Decimal(str(scale)))

    protein = None
    fat = None
    fiber = None
    for fn in food.food_nutrients:
        scaled = float(fn.amount_per_serving * Decimal(str(scale)))
        name_lower = fn.nutrient.name.lower()
        if name_lower == "protein":
            protein = scaled
        elif name_lower in ["total lipid (fat)", "fat"]:
            fat = scaled
        elif name_lower in ["fiber, total dietary", "fiber"]:
            fiber = scaled

    friendly = {
        "calories": calories or 0,
        "protein": protein or 0,
        "carbs": carbs or 0,
        "fat": fat or 0,
        "fiber": fiber or 0,
    }

    summary = []
    for cfg in config_items:
        if cfg.formula:
            val = evaluate_formula(cfg.formula, friendly) or 0
        elif cfg.nutrient_id:
            if cfg.nutrient_id in ENERGY_NUTRIENT_IDS:
                val = _coalesce_energy(food.food_nutrients, Decimal(str(scale))) or 0
            elif cfg.nutrient_id in CARB_NUTRIENT_IDS:
                val = _coalesce_carbs(food.food_nutrients, Decimal(str(scale))) or 0
            else:
                val = 0
                for fn in food.food_nutrients:
                    if fn.nutrient_id == cfg.nutrient_id:
                        val = float(fn.amount_per_serving * Decimal(str(scale)))
                        break
        else:
            val = 0
        summary.append({
            "name": cfg.display_name,
            "value": round(val, 1),
            "unit": cfg.display_unit,
        })

    return summary


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

        # Group logs by meal
        # Load user summary config early (needed for per-log summary)
        from whati8.api.routers.summary_config import _ensure_defaults
        from whati8.services.formula_engine import evaluate_formula
        config_items = await _ensure_defaults(db, user_id)

        meal_groups = []
        for meal in all_meals:
            meal_logs = [log for log in logs if log.meal_id == meal.id]

            # Convert logs to response format with computed nutrients
            formatted_logs = []
            for log in meal_logs:
                # Compute key nutrients for display
                portion_scale_factor = _portion_scale(log, log.food)
                
                # Apply coalesce strategies
                calories = _coalesce_energy(log.food.food_nutrients, portion_scale_factor)
                carbs = _coalesce_carbs(log.food.food_nutrients, portion_scale_factor)
                
                protein = None
                fat = None
                fiber = None

                for fn in log.food.food_nutrients:
                    # Scale by quantity
                    scaled_value = float(fn.amount_per_serving * portion_scale_factor)

                    if fn.nutrient.name.lower() == "protein":
                        protein = scaled_value
                    elif fn.nutrient.name.lower() in ["total lipid (fat)", "fat"]:
                        fat = scaled_value
                    elif fn.nutrient.name.lower() in ["fiber, total dietary", "fiber"]:
                        fiber = scaled_value

                # Build friendly values for formula evaluation
                friendly = {
                    "calories": calories or 0,
                    "protein": protein or 0,
                    "carbs": carbs or 0,
                    "fat": fat or 0,
                    "fiber": fiber or 0,
                }

                # Compute per-log summary nutrients matching user config
                log_summary = []
                for cfg in config_items:
                    if cfg.formula:
                        val = evaluate_formula(cfg.formula, friendly) or 0
                    elif cfg.nutrient_id:
                        # Apply coalesce strategies for special nutrient IDs
                        if cfg.nutrient_id in ENERGY_NUTRIENT_IDS:
                            val = _coalesce_energy(log.food.food_nutrients, portion_scale_factor) or 0
                        elif cfg.nutrient_id in CARB_NUTRIENT_IDS:
                            val = _coalesce_carbs(log.food.food_nutrients, portion_scale_factor) or 0
                        else:
                            # Find the matching nutrient total for this log
                            val = 0
                            for fn2 in log.food.food_nutrients:
                                if fn2.nutrient_id == cfg.nutrient_id:
                                    sv = float(fn2.amount_per_serving * portion_scale_factor)
                                    val = sv
                                    break
                    else:
                        val = 0
                    log_summary.append({
                        "name": cfg.display_name,
                        "value": round(val, 1),
                        "unit": cfg.display_unit,
                    })

                formatted_logs.append({
                    "id": log.id,
                    "food_id": log.food_id,
                    "food_name": log.food.name,
                    "quantity": float(log.quantity),
                    "unit": log.unit or log.food.unit,
                    "logged_at": log.logged_at,
                    "calories": calories,
                    "protein": protein,
                    "carbs": carbs,
                    "fat": fat,
                    "fiber": fiber,
                    "summary_nutrients": log_summary,
                })

            if meal_logs:  # Only include meals that have logs
                meal_groups.append({
                    "meal": {
                        "id": meal.id,
                        "name": meal.name,
                        "display_order": meal.display_order,
                    },
                    "logs": formatted_logs,
                })

        # Add ungrouped logs (null meal_id)
        ungrouped_logs = [log for log in logs if log.meal_id is None]
        if ungrouped_logs:
            formatted_ungrouped = []
            for log in ungrouped_logs:
                portion_scale_factor = _portion_scale(log, log.food)
                
                # Apply coalesce strategies
                calories = _coalesce_energy(log.food.food_nutrients, portion_scale_factor)
                carbs = _coalesce_carbs(log.food.food_nutrients, portion_scale_factor)
                
                protein = fat = fiber = None
                for fn in log.food.food_nutrients:
                    scaled_value = float(fn.amount_per_serving * portion_scale_factor)
                    if fn.nutrient.name.lower() == "protein":
                        protein = scaled_value
                    elif fn.nutrient.name.lower() in ["total lipid (fat)", "fat"]:
                        fat = scaled_value
                    elif fn.nutrient.name.lower() in ["fiber, total dietary", "fiber"]:
                        fiber = scaled_value

                friendly = {"calories": calories or 0, "protein": protein or 0, "carbs": carbs or 0, "fat": fat or 0, "fiber": fiber or 0}
                log_summary = []
                for cfg in config_items:
                    if cfg.formula:
                        val = evaluate_formula(cfg.formula, friendly) or 0
                    elif cfg.nutrient_id:
                        # Apply coalesce strategies for special nutrient IDs
                        if cfg.nutrient_id in ENERGY_NUTRIENT_IDS:
                            val = _coalesce_energy(log.food.food_nutrients, portion_scale_factor) or 0
                        elif cfg.nutrient_id in CARB_NUTRIENT_IDS:
                            val = _coalesce_carbs(log.food.food_nutrients, portion_scale_factor) or 0
                        else:
                            val = 0
                            for fn2 in log.food.food_nutrients:
                                if fn2.nutrient_id == cfg.nutrient_id:
                                    sv = float(fn2.amount_per_serving * portion_scale_factor)
                                    val = sv
                                    break
                    else:
                        val = 0
                    log_summary.append({"name": cfg.display_name, "value": round(val, 1), "unit": cfg.display_unit})

                formatted_ungrouped.append({
                    "id": log.id,
                    "food_id": log.food_id,
                    "food_name": log.food.name,
                    "quantity": float(log.quantity),
                    "unit": log.unit or log.food.unit,
                    "logged_at": log.logged_at,
                    "calories": calories,
                    "protein": protein,
                    "carbs": carbs,
                    "fat": fat,
                    "fiber": fiber,
                    "summary_nutrients": log_summary,
                })
            meal_groups.append({
                "meal": {
                    "id": 0,
                    "name": "Other",
                    "display_order": 999,
                },
                "logs": formatted_ungrouped,
            })

        # Calculate daily nutrient totals with friendly names
        from whati8.services.formula_engine import get_friendly_name, FRIENDLY_TO_USDA
        # Build set of nutrient IDs we care about from user's summary config
        # Get user's summary config (auto-create defaults if empty)
        from whati8.api.routers.summary_config import _ensure_defaults
        config_items = await _ensure_defaults(db, user_id)
        # Nutrient IDs from user config (for standard nutrients)
        config_nutrient_ids = {c.nutrient_id for c in config_items if c.nutrient_id}
        # If any energy nutrient is in config, include all energy variants
        if config_nutrient_ids & ENERGY_NUTRIENT_IDS:
            config_nutrient_ids |= ENERGY_NUTRIENT_IDS
        # If any formulas exist, don't filter — we need all nutrients for formula evaluation
        has_formulas = any(c.formula for c in config_items)

        nutrient_totals = {}
        for log in logs:
            for fn in log.food.food_nutrients:
                nutrient_id = fn.nutrient_id
                if config_nutrient_ids and not has_formulas and nutrient_id not in config_nutrient_ids:
                    continue
                nutrient_id = fn.nutrient_id
                scaled_value = float(fn.amount_per_serving * _portion_scale(log, log.food))
                friendly_name, friendly_unit = get_friendly_name(fn.nutrient.name)

                if nutrient_id not in nutrient_totals:
                    nutrient_totals[nutrient_id] = {
                        "nutrient_id": nutrient_id,
                        "name": friendly_name,
                        "unit": friendly_unit,
                        "raw_unit": fn.nutrient.unit,
                        "value": 0.0,
                        "target": None,
                    }

                nutrient_totals[nutrient_id]["value"] += scaled_value

        # Build summary using user's configured metrics
        from whati8.services.formula_engine import evaluate_formula
        # config_items already loaded above for nutrient ID filtering

        # If no config, use all computed nutrient_totals as fallback
        if not config_items:
            summary_nutrients = list(nutrient_totals.values())
        else:
            # Build friendly-name lookup for formulas
            friendly_values: dict[str, float] = {}
            for nid, data in nutrient_totals.items():
                # Map back to friendly keys
                for friendly_key, usda_name in FRIENDLY_TO_USDA.items():
                    fn, _ = get_friendly_name(usda_name)
                    if data["name"] == fn:
                        val = data["value"]
                        friendly_values[friendly_key] = val

            # Pre-compute per-log friendly values for formula metrics
            # Formulas are nonlinear (rounding), so f(a)+f(b) != f(a+b)
            # We must evaluate per-log and sum the results
            per_log_friendly: list[dict[str, float]] = []
            for log in logs:
                log_vals: dict[str, float] = {}
                for fn in log.food.food_nutrients:
                    scaled = float(fn.amount_per_serving * _portion_scale(log, log.food))
                    fn_friendly, _ = get_friendly_name(fn.nutrient.name)
                    for fkey, usda_name in FRIENDLY_TO_USDA.items():
                        fn2, _ = get_friendly_name(usda_name)
                        if fn_friendly == fn2:
                            log_vals[fkey] = log_vals.get(fkey, 0) + scaled
                per_log_friendly.append(log_vals)

            summary_nutrients = []
            for item in config_items:
                if item.formula:
                    # Sum per-log formula evaluations (nonlinear formulas like WW points)
                    value = sum(evaluate_formula(item.formula, lv) or 0.0 for lv in per_log_friendly)
                elif item.nutrient_id:
                    # Standard nutrient — look up in totals
                    value = nutrient_totals.get(item.nutrient_id, {}).get("value", 0.0)
                else:
                    value = 0.0

                summary_nutrients.append({
                    "nutrient_id": item.nutrient_id or 0,
                    "name": item.display_name or "Unknown",
                    "unit": item.display_unit or "",
                    "value": round(value, 1),
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
