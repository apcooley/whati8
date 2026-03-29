"""Service layer for recipe CRUD, nutrition calculation, and versioning."""

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from whati8.logging_config import get_logger
from whati8.models import Food, FoodNutrient, FoodPortion
from whati8.models.recipe import Recipe, RecipeIngredient, RecipeVersion
from whati8.models.user_food import UserFood

logger = get_logger(__name__)


class RecipeService:
    """Service for recipe management with versioning and cascade updates."""

    @staticmethod
    async def create_recipe(
        db: AsyncSession,
        user_id: int,
        name: str,
        servings: float,
        serving_unit: str,
        ingredients: list[dict[str, Any]],
    ) -> Recipe:
        """
        Create a recipe with ingredients and materialize as a Food.

        Args:
            db: Database session
            user_id: Owner user ID
            name: Recipe name
            servings: Number of servings
            serving_unit: Unit name for servings (e.g., "slice", "bowl")
            ingredients: List of dicts with food_id, quantity, unit, portion_description

        Returns:
            The created Recipe object with current_food_id set
        """
        # Create recipe record
        recipe = Recipe(
            user_id=user_id,
            name=name,
            servings=Decimal(str(servings)),
            serving_unit=serving_unit,
            current_version=1,
        )
        db.add(recipe)
        await db.flush()

        # Add ingredients
        for ing in ingredients:
            recipe_ingredient = RecipeIngredient(
                recipe_id=recipe.id,
                food_id=ing["food_id"],
                quantity=Decimal(str(ing["quantity"])),
                unit=ing["unit"],
                portion_description=ing.get("portion_description"),
            )
            db.add(recipe_ingredient)

        await db.flush()

        # Materialize as food
        food = await RecipeService._materialize_recipe(db, recipe, user_id, version=1)
        recipe.current_food_id = food.id

        # Create recipe version entry
        recipe_version = RecipeVersion(
            recipe_id=recipe.id,
            version=1,
            food_id=food.id,
        )
        db.add(recipe_version)

        # Auto-register in UserFood
        user_food = UserFood(
            user_id=user_id,
            food_id=food.id,
            default_quantity=Decimal("1"),
        )
        db.add(user_food)

        await db.commit()
        await db.refresh(recipe)

        logger.info(f"Created recipe {recipe.id} '{name}' with {len(ingredients)} ingredients")
        return recipe

    @staticmethod
    async def add_ingredient(
        db: AsyncSession,
        recipe_id: int,
        user_id: int,
        food_id: int,
        quantity: float,
        unit: str,
        portion_description: str | None = None,
    ) -> RecipeIngredient:
        """
        Add an ingredient to a recipe, creating a new version.

        Checks for circular dependencies before adding.
        Creates a new materialized food version and cascades to parent recipes.

        Args:
            db: Database session
            recipe_id: Target recipe ID
            user_id: User ID (for ownership check)
            food_id: Food to add as ingredient
            quantity: Amount
            unit: Unit of measurement
            portion_description: Optional portion description

        Returns:
            The created RecipeIngredient

        Raises:
            ValueError: If circular dependency detected
        """
        # Get recipe
        recipe = await db.get(Recipe, recipe_id)
        if not recipe or recipe.user_id != user_id:
            raise ValueError("Recipe not found or access denied")

        # Check circular dependency FIRST
        food = await db.get(Food, food_id, options=[selectinload(Food.portions)])
        if not food:
            raise ValueError("Food not found")

        if food.recipe_id is not None:
            # Food is a recipe-food, check for cycles
            await RecipeService._check_circular_dependency(db, recipe_id, food.recipe_id)

        # Add the ingredient
        ingredient = RecipeIngredient(
            recipe_id=recipe_id,
            food_id=food_id,
            quantity=Decimal(str(quantity)),
            unit=unit,
            portion_description=portion_description,
        )
        db.add(ingredient)
        await db.flush()

        # Increment version and re-materialize
        new_version = recipe.current_version + 1
        old_food_id = recipe.current_food_id

        # Mark old food as expired
        if old_food_id:
            old_food = await db.get(Food, old_food_id)
            if old_food:
                old_food.is_recipe_expired = True

        # Create new materialized food
        new_food = await RecipeService._materialize_recipe(db, recipe, user_id, version=new_version)
        recipe.current_version = new_version
        recipe.current_food_id = new_food.id

        # Create recipe version entry
        recipe_version = RecipeVersion(
            recipe_id=recipe_id,
            version=new_version,
            food_id=new_food.id,
        )
        db.add(recipe_version)

        # Update UserFood to point to new food
        result = await db.execute(
            select(UserFood).where(
                UserFood.user_id == user_id,
                UserFood.food_id == old_food_id,
            )
        )
        user_food = result.scalar_one_or_none()
        if user_food:
            user_food.food_id = new_food.id

        await db.flush()

        # Cascade to parent recipes
        await RecipeService._cascade_to_parents(db, recipe_id, user_id)

        await db.commit()
        await db.refresh(ingredient)

        logger.info(f"Added ingredient to recipe {recipe_id}, new version {new_version}")
        return ingredient

    @staticmethod
    async def update_metadata(
        db: AsyncSession,
        recipe_id: int,
        user_id: int,
        name: str | None = None,
        servings: float | None = None,
        serving_unit: str | None = None,
    ) -> Recipe:
        """
        Update recipe metadata (name, servings, serving_unit).

        Does NOT create a new version. If servings changed, recalculates
        nutrition on the existing food.

        Args:
            db: Database session
            recipe_id: Recipe ID
            user_id: User ID (for ownership check)
            name: New name (optional)
            servings: New servings count (optional)
            serving_unit: New serving unit (optional)

        Returns:
            Updated Recipe object
        """
        recipe = await db.get(Recipe, recipe_id)
        if not recipe or recipe.user_id != user_id:
            raise ValueError("Recipe not found or access denied")

        servings_changed = False

        if name is not None:
            recipe.name = name

        if servings is not None:
            old_servings = recipe.servings
            recipe.servings = Decimal(str(servings))
            servings_changed = (old_servings != recipe.servings)

        if serving_unit is not None:
            recipe.serving_unit = serving_unit

        await db.flush()

        # If servings changed, recalculate nutrition on existing food
        if servings_changed and recipe.current_food_id:
            food = await db.get(Food, recipe.current_food_id)
            if food:
                # Update food name if recipe name changed
                if name is not None:
                    food.name = name

                # Recalculate nutrition
                await RecipeService._recalculate_food_nutrition(db, recipe, food)

        elif name is not None and recipe.current_food_id:
            # Just update food name
            food = await db.get(Food, recipe.current_food_id)
            if food:
                food.name = name

        await db.commit()
        await db.refresh(recipe)

        logger.info(f"Updated metadata for recipe {recipe_id}")
        return recipe

    @staticmethod
    async def _materialize_recipe(
        db: AsyncSession,
        recipe: Recipe,
        user_id: int,
        version: int,
    ) -> Food:
        """
        Materialize a recipe as a Food entry with nutrition and portions.

        Calculates total nutrition from ingredients, divides by servings,
        creates FoodNutrient entries, and FoodPortions.

        Args:
            db: Database session
            recipe: Recipe to materialize
            user_id: User ID
            version: Recipe version number

        Returns:
            The created Food object
        """
        # Load ingredients with their foods and nutrients
        result = await db.execute(
            select(RecipeIngredient)
            .where(RecipeIngredient.recipe_id == recipe.id)
            .options(
                selectinload(RecipeIngredient.food)
                .selectinload(Food.food_nutrients)
                .selectinload(FoodNutrient.nutrient),
                selectinload(RecipeIngredient.food).selectinload(Food.portions),
            )
        )
        ingredients = list(result.scalars().all())

        # Re-query each ingredient food's nutrients directly from DB
        # to avoid stale session cache (expire_on_commit=False can cause
        # food_nutrients to accumulate stale entries across recipe operations)
        _fresh_nutrients: dict[int, list] = {}
        for ingredient in ingredients:
            fid = ingredient.food_id
            if fid not in _fresh_nutrients:
                _fn_result = await db.execute(
                    select(FoodNutrient)
                    .where(FoodNutrient.food_id == fid)
                    .options(selectinload(FoodNutrient.nutrient))
                    .execution_options(populate_existing=True)
                )
                _fresh_nutrients[fid] = list(_fn_result.unique().scalars().all())

        # Calculate total weight and nutrients
        total_weight = Decimal("0")
        nutrient_totals: dict[int, Decimal] = {}

        from whati8.services.nutrient_calculator import (
            NutrientInput as CalcInput,
            compute_item_nutrients,
            _is_energy,
            _is_carb,
        )

        # ── Pass 1: determine a SINGLE global canonical ID for energy and carbs ──
        # Different ingredients may have different "winning" energy/carb variants
        # (e.g., USDA has Atwater General; custom food has plain Energy only).
        # We pick ONE canonical ID per category for the whole recipe so the
        # materialized food always has exactly one energy and one carb FoodNutrient.
        #
        # Energy priority (by name): Atwater General > Atwater Specific > plain
        # Carb priority (by name): by summation > by difference > generic
        global_energy_id: int | None = None
        global_energy_priority: int = 99  # lower = better
        global_carb_id: int | None = None
        global_carb_priority: int = 99

        for ingredient in ingredients:
            food_nutrients_fresh = _fresh_nutrients.get(ingredient.food.id, ingredient.food.food_nutrients)
            for fn in food_nutrients_fresh:
                name = fn.nutrient.name
                name_lower = name.lower()
                if _is_energy(name):
                    if "atwater general" in name_lower:
                        priority = 0
                    elif "atwater specific" in name_lower:
                        priority = 1
                    else:
                        priority = 2
                    if priority < global_energy_priority:
                        global_energy_priority = priority
                        global_energy_id = fn.nutrient_id
                elif _is_carb(name):
                    if "summation" in name_lower:
                        priority = 0
                    elif "difference" in name_lower:
                        priority = 1
                    else:
                        priority = 2
                    if priority < global_carb_priority:
                        global_carb_priority = priority
                        global_carb_id = fn.nutrient_id

        # ── Pass 2: accumulate nutrients per ingredient ───────────────────────────
        for ingredient in ingredients:
            food = ingredient.food
            # Use fresh nutrients from DB, not potentially stale session cache
            food_nutrients_fresh = _fresh_nutrients.get(food.id, food.food_nutrients)

            # Temporarily replace food_nutrients with fresh ones for the calculator
            original_food_nutrients = food.food_nutrients
            food.food_nutrients = food_nutrients_fresh

            # Calculate weight in grams
            quantity_in_grams = await RecipeService._get_quantity_in_grams(
                db, ingredient
            )
            total_weight += quantity_in_grams

            # Use NutrientCalculator to get coalesced friendly values and per-id amounts
            calc_input = CalcInput(
                food=food,
                quantity=float(quantity_in_grams),
                unit="grams",
            )
            friendly, by_id = compute_item_nutrients(calc_input)

            # Restore original food_nutrients
            food.food_nutrients = original_food_nutrients

            # Collect all energy/carb IDs for this ingredient (to skip in general loop)
            _energy_ids: set[int] = set()
            _carb_ids: set[int] = set()
            for fn in food_nutrients_fresh:
                name = fn.nutrient.name
                if _is_energy(name):
                    _energy_ids.add(fn.nutrient_id)
                elif _is_carb(name):
                    _carb_ids.add(fn.nutrient_id)

            # Accumulate coalesced energy under GLOBAL canonical ID
            coalesced_energy = friendly["calories"]
            if coalesced_energy and global_energy_id is not None:
                if global_energy_id not in nutrient_totals:
                    nutrient_totals[global_energy_id] = Decimal("0")
                nutrient_totals[global_energy_id] += Decimal(str(coalesced_energy))

            # Accumulate coalesced carbs under GLOBAL canonical ID
            coalesced_carbs = friendly["carbs"]
            if coalesced_carbs and global_carb_id is not None:
                if global_carb_id not in nutrient_totals:
                    nutrient_totals[global_carb_id] = Decimal("0")
                nutrient_totals[global_carb_id] += Decimal(str(coalesced_carbs))

            # Accumulate all other (non-energy, non-carb) nutrients from by_id
            skip_ids = _energy_ids | _carb_ids
            for nutrient_id, amount in by_id.items():
                if nutrient_id in skip_ids:
                    continue
                if nutrient_id not in nutrient_totals:
                    nutrient_totals[nutrient_id] = Decimal("0")
                nutrient_totals[nutrient_id] += Decimal(str(amount))

        # Create Food entry
        serving_size = total_weight / recipe.servings
        food = Food(
            name=recipe.name,
            serving_size=serving_size,
            unit="g",
            created_by_user_id=user_id,
            recipe_id=recipe.id,
            recipe_version=version,
            is_recipe_expired=False,
        )
        db.add(food)
        await db.flush()

        # Create FoodNutrient entries (per serving)
        for nutrient_id, total_amount in nutrient_totals.items():
            per_serving = total_amount / recipe.servings
            food_nutrient = FoodNutrient(
                food_id=food.id,
                nutrient_id=nutrient_id,
                amount_per_serving=per_serving,
            )
            db.add(food_nutrient)

        # Create FoodPortions: serving_unit, grams, oz
        # 1. Serving unit (e.g., "slice")
        portion_serving = FoodPortion(
            food_id=food.id,
            amount=Decimal("1"),
            unit_name=recipe.serving_unit,
            gram_weight=serving_size,
            portion_description=recipe.serving_unit,
            sequence_number=1,
        )
        db.add(portion_serving)

        # 2. Grams
        portion_grams = FoodPortion(
            food_id=food.id,
            amount=Decimal("1"),
            unit_name="g",
            gram_weight=Decimal("1"),
            portion_description="grams",
            sequence_number=2,
        )
        db.add(portion_grams)

        # 3. Ounces
        portion_oz = FoodPortion(
            food_id=food.id,
            amount=Decimal("1"),
            unit_name="oz",
            gram_weight=Decimal("28.35"),
            portion_description="ounces",
            sequence_number=3,
        )
        db.add(portion_oz)

        await db.flush()

        return food

    @staticmethod
    async def _get_quantity_in_grams(
        db: AsyncSession,
        ingredient: RecipeIngredient,
    ) -> Decimal:
        """
        Convert ingredient quantity to grams.

        For tests, all portions have gram_weight=1, so quantity IS grams.
        In general, looks up the portion to find gram_weight.

        Args:
            db: Database session
            ingredient: RecipeIngredient with food loaded

        Returns:
            Quantity in grams
        """
        # If unit is "grams" or "g", quantity IS grams
        if ingredient.unit.lower() in ("grams", "g"):
            return ingredient.quantity

        # Look up portion
        food = ingredient.food
        if not food.portions:
            # No portions, assume quantity is grams
            return ingredient.quantity

        import re

        def normalize(s):
            """Normalize portion description for matching.
            Strips '1.0 undetermined' prefix and normalizes '.0g' → 'g'."""
            s = re.sub(r'^[\d.]+ undetermined ', '', s)
            s = re.sub(r'(\d+)\.0g\)', lambda m: m.group(1) + 'g)', s)
            return s.strip().lower()

        ing_unit_norm = normalize(ingredient.unit)
        ing_desc_norm = normalize(ingredient.portion_description or ingredient.unit)

        # Find matching portion
        for portion in food.portions:
            p_desc_norm = normalize(portion.portion_description or '')
            p_unit_norm = (portion.unit_name or '').lower()

            # Match by normalized description
            if p_desc_norm and (p_desc_norm == ing_unit_norm or p_desc_norm == ing_desc_norm):
                return ingredient.quantity * portion.gram_weight

            # Match by unit_name
            if p_unit_norm and (p_unit_norm == ing_unit_norm or p_unit_norm == ingredient.unit.lower()):
                return ingredient.quantity * portion.gram_weight

        # Default: assume quantity is grams
        return ingredient.quantity

    @staticmethod
    async def _check_circular_dependency(
        db: AsyncSession,
        recipe_id: int,
        food_recipe_id: int,
    ) -> None:
        """
        Check if adding a recipe-food would create a circular dependency.

        Walks the dependency chain recursively to detect cycles.

        Args:
            db: Database session
            recipe_id: The recipe we're adding to
            food_recipe_id: The recipe_id of the food being added

        Raises:
            ValueError: If circular dependency detected
        """
        visited = set()
        await RecipeService._check_cycle(db, recipe_id, food_recipe_id, visited)

    @staticmethod
    async def _check_cycle(
        db: AsyncSession,
        target_recipe_id: int,
        current_recipe_id: int,
        visited: set[int],
    ) -> None:
        """
        Recursive cycle detection.

        Args:
            db: Database session
            target_recipe_id: The recipe we're trying to add to
            current_recipe_id: The recipe we're currently checking
            visited: Set of visited recipe IDs

        Raises:
            ValueError: If cycle detected
        """
        if current_recipe_id == target_recipe_id:
            raise ValueError("Circular dependency detected")

        if current_recipe_id in visited:
            return

        visited.add(current_recipe_id)

        # Get ingredients of current recipe
        result = await db.execute(
            select(RecipeIngredient)
            .where(RecipeIngredient.recipe_id == current_recipe_id)
            .options(selectinload(RecipeIngredient.food))
        )
        ingredients = list(result.scalars().all())

        # Check each ingredient
        for ingredient in ingredients:
            if ingredient.food.recipe_id is not None:
                # This ingredient is a recipe-food, recurse
                await RecipeService._check_cycle(
                    db, target_recipe_id, ingredient.food.recipe_id, visited
                )

    @staticmethod
    async def _cascade_to_parents(
        db: AsyncSession,
        child_recipe_id: int,
        user_id: int,
    ) -> None:
        """
        Cascade updates to parent recipes that use this recipe as an ingredient.

        After re-materializing a recipe, find all recipes that use it and
        re-materialize them as well (creating new versions).

        Args:
            db: Database session
            child_recipe_id: The recipe that was updated
            user_id: User ID
        """
        # Find parent recipes whose ingredients reference foods with recipe_id = child_recipe_id
        result = await db.execute(
            select(RecipeIngredient.recipe_id.distinct())
            .join(Food, RecipeIngredient.food_id == Food.id)
            .where(Food.recipe_id == child_recipe_id)
        )
        parent_recipe_ids = list(result.scalars().all())

        for parent_recipe_id in parent_recipe_ids:
            # Get parent recipe
            parent_recipe = await db.get(Recipe, parent_recipe_id)
            if not parent_recipe:
                continue

            # Get child recipe's new food_id
            child_recipe = await db.get(Recipe, child_recipe_id)
            new_child_food_id = child_recipe.current_food_id

            # Update parent's ingredients to reference new child food
            result = await db.execute(
                select(RecipeIngredient)
                .join(Food, RecipeIngredient.food_id == Food.id)
                .where(
                    RecipeIngredient.recipe_id == parent_recipe_id,
                    Food.recipe_id == child_recipe_id,
                )
            )
            ingredients_to_update = list(result.scalars().all())

            for ingredient in ingredients_to_update:
                ingredient.food_id = new_child_food_id

            await db.flush()

            # Increment version and re-materialize parent
            new_version = parent_recipe.current_version + 1
            old_food_id = parent_recipe.current_food_id

            # Mark old food as expired
            if old_food_id:
                old_food = await db.get(Food, old_food_id)
                if old_food:
                    old_food.is_recipe_expired = True

            # Create new materialized food
            new_food = await RecipeService._materialize_recipe(
                db, parent_recipe, parent_recipe.user_id, version=new_version
            )
            parent_recipe.current_version = new_version
            parent_recipe.current_food_id = new_food.id

            # Create recipe version entry
            recipe_version = RecipeVersion(
                recipe_id=parent_recipe_id,
                version=new_version,
                food_id=new_food.id,
            )
            db.add(recipe_version)

            # Update UserFood to point to new food
            result = await db.execute(
                select(UserFood).where(
                    UserFood.user_id == parent_recipe.user_id,
                    UserFood.food_id == old_food_id,
                )
            )
            user_food = result.scalar_one_or_none()
            if user_food:
                user_food.food_id = new_food.id

            await db.flush()

            # Recursively cascade to grandparents
            await RecipeService._cascade_to_parents(db, parent_recipe_id, parent_recipe.user_id)

    @staticmethod
    async def _recalculate_food_nutrition(
        db: AsyncSession,
        recipe: Recipe,
        food: Food,
    ) -> None:
        """
        Recalculate nutrition for an existing food when servings change.

        Does NOT create a new food or version. Updates FoodNutrient entries
        and food.serving_size in place.

        Args:
            db: Database session
            recipe: Recipe with updated servings
            food: Existing food to update
        """
        # Load ingredients with their foods and nutrients
        result = await db.execute(
            select(RecipeIngredient)
            .where(RecipeIngredient.recipe_id == recipe.id)
            .options(
                selectinload(RecipeIngredient.food)
                .selectinload(Food.food_nutrients)
                .selectinload(FoodNutrient.nutrient),
                selectinload(RecipeIngredient.food).selectinload(Food.portions),
            )
        )
        ingredients = list(result.scalars().all())

        # Calculate total weight and nutrients
        total_weight = Decimal("0")
        nutrient_totals: dict[int, Decimal] = {}

        for ingredient in ingredients:
            ing_food = ingredient.food

            # Calculate weight in grams
            quantity_in_grams = await RecipeService._get_quantity_in_grams(
                db, ingredient
            )
            total_weight += quantity_in_grams

            # Calculate nutrients
            for food_nutrient in ing_food.food_nutrients:
                nutrient_id = food_nutrient.nutrient_id

                # Get nutrient per gram
                if ing_food.created_by_user_id:
                    # Custom food: amount_per_serving is per serving_size
                    nutrient_per_gram = food_nutrient.amount_per_serving / ing_food.serving_size
                else:
                    # USDA food: amount_per_serving is per 100g
                    nutrient_per_gram = food_nutrient.amount_per_serving / Decimal("100")

                # Total nutrient from this ingredient
                nutrient_amount = nutrient_per_gram * quantity_in_grams

                if nutrient_id not in nutrient_totals:
                    nutrient_totals[nutrient_id] = Decimal("0")
                nutrient_totals[nutrient_id] += nutrient_amount

        # Update food serving_size
        food.serving_size = total_weight / recipe.servings

        # Update FoodNutrient entries
        for nutrient_id, total_amount in nutrient_totals.items():
            per_serving = total_amount / recipe.servings

            # Find existing FoodNutrient
            result = await db.execute(
                select(FoodNutrient).where(
                    FoodNutrient.food_id == food.id,
                    FoodNutrient.nutrient_id == nutrient_id,
                )
            )
            food_nutrient = result.scalar_one_or_none()

            if food_nutrient:
                food_nutrient.amount_per_serving = per_serving
            else:
                # Create new one (shouldn't happen, but handle it)
                food_nutrient = FoodNutrient(
                    food_id=food.id,
                    nutrient_id=nutrient_id,
                    amount_per_serving=per_serving,
                )
                db.add(food_nutrient)

        # Update FoodPortion for serving unit to reflect new serving_size
        result = await db.execute(
            select(FoodPortion).where(
                FoodPortion.food_id == food.id,
                FoodPortion.unit_name == recipe.serving_unit,
            )
        )
        portion = result.scalar_one_or_none()
        if portion:
            portion.gram_weight = food.serving_size

        await db.flush()
