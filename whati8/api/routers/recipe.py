"""
Recipe API endpoints.

Provides endpoints for creating, reading, updating, and managing recipes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from whati8.api.deps import get_current_user, get_db
from whati8.models import Food, FoodNutrient, User
from whati8.models.recipe import Recipe, RecipeIngredient
from whati8.schemas.recipe import (
    DependencyCheckResponse,
    PerServingNutrition,
    RecipeCreateRequest,
    RecipeIngredientCreate,
    RecipeIngredientResponse,
    RecipeResponse,
    RecipeUpdateRequest,
)
from whati8.services.recipe_service import RecipeService

router = APIRouter(prefix="/recipes", tags=["recipes"])


async def _load_recipe_with_details(db: AsyncSession, recipe_id: int) -> Recipe:
    """Load a recipe with all relationships for response serialization."""
    query = (
        select(Recipe)
        .options(
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.food),
        )
        .where(Recipe.id == recipe_id)
    )
    result = await db.execute(query)
    recipe = result.scalar_one_or_none()
    return recipe


async def _get_per_serving_nutrition(db: AsyncSession, food_id: int) -> PerServingNutrition:
    """Get per-serving nutrition for a food."""
    # Load the food with serving_size
    food = await db.get(Food, food_id)
    if not food:
        raise HTTPException(status_code=404, detail="Food not found")

    # Load nutrients
    result = await db.execute(
        select(FoodNutrient)
        .options(selectinload(FoodNutrient.nutrient))
        .where(FoodNutrient.food_id == food_id)
    )
    food_nutrients = list(result.scalars().all())

    # Map nutrients to response
    nutrition = {
        "calories": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": 0.0,
        "weight_g": float(food.serving_size),
    }

    for fn in food_nutrients:
        nutrient_name = fn.nutrient.name
        amount = float(fn.amount_per_serving)

        # Map nutrient names to response fields
        if "Energy" in nutrient_name or "Calories" in nutrient_name:
            nutrition["calories"] = amount
        elif "Protein" in nutrient_name:
            nutrition["protein_g"] = amount
        elif "Carbohydrate" in nutrient_name:
            nutrition["carbs_g"] = amount
        elif "Fat" in nutrient_name or "lipid" in nutrient_name.lower():
            nutrition["fat_g"] = amount
        elif "Fiber" in nutrient_name or "fibre" in nutrient_name.lower():
            nutrition["fiber_g"] = amount

    return PerServingNutrition(**nutrition)


def _build_recipe_response(recipe: Recipe, per_serving: PerServingNutrition) -> RecipeResponse:
    """Build a RecipeResponse from a Recipe object."""
    ingredients_response = []
    for ing in recipe.ingredients:
        ingredients_response.append(
            RecipeIngredientResponse(
                id=ing.recipe_ingredient_id,
                food_id=ing.food_id,
                food_name=ing.food.name,
                quantity=float(ing.quantity),
                unit=ing.unit,
                portion_description=ing.portion_description,
            )
        )

    return RecipeResponse(
        id=recipe.id,
        name=recipe.name,
        servings=float(recipe.servings),
        serving_unit=recipe.serving_unit,
        current_version=recipe.current_version,
        food_id=recipe.current_food_id,
        ingredients=ingredients_response,
        per_serving=per_serving,
    )


@router.post("/", response_model=RecipeResponse, status_code=status.HTTP_200_OK)
async def create_recipe(
    recipe_data: RecipeCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new recipe.

    Creates a recipe with ingredients and materializes it as a Food.
    Returns the created recipe with per-serving nutrition.

    **Authentication required.**
    """
    # Validate that all food_ids exist
    for ing in recipe_data.ingredients:
        food = await db.get(Food, ing.food_id)
        if not food:
            raise HTTPException(
                status_code=404,
                detail=f"Food with id {ing.food_id} not found",
            )

    # Convert to service format
    ingredients = [
        {
            "food_id": ing.food_id,
            "quantity": ing.quantity,
            "unit": ing.unit,
            "portion_description": ing.portion_description,
        }
        for ing in recipe_data.ingredients
    ]

    try:
        recipe = await RecipeService.create_recipe(
            db=db,
            user_id=current_user.id,
            name=recipe_data.name,
            servings=recipe_data.servings,
            serving_unit=recipe_data.serving_unit,
            ingredients=ingredients,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Reload with relationships
    recipe = await _load_recipe_with_details(db, recipe.id)

    # Get per-serving nutrition
    per_serving = await _get_per_serving_nutrition(db, recipe.current_food_id)

    return _build_recipe_response(recipe, per_serving)


@router.get("/", response_model=list[RecipeResponse])
async def list_recipes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all recipes for the current user.

    Returns all recipes created by the authenticated user.

    **Authentication required.**
    """
    query = (
        select(Recipe)
        .options(
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.food),
        )
        .where(Recipe.user_id == current_user.id)
        .order_by(Recipe.created_at.desc())
    )
    result = await db.execute(query)
    recipes = list(result.scalars().all())

    # Build responses
    responses = []
    for recipe in recipes:
        per_serving = await _get_per_serving_nutrition(db, recipe.current_food_id)
        responses.append(_build_recipe_response(recipe, per_serving))

    return responses


@router.get("/{recipe_id}", response_model=RecipeResponse)
async def get_recipe(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a recipe by ID.

    Returns the recipe with ingredients and per-serving nutrition.

    **Authentication required.**
    """
    recipe = await _load_recipe_with_details(db, recipe_id)

    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    if recipe.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    per_serving = await _get_per_serving_nutrition(db, recipe.current_food_id)

    return _build_recipe_response(recipe, per_serving)


@router.put("/{recipe_id}", response_model=RecipeResponse)
async def update_recipe(
    recipe_id: int,
    update_data: RecipeUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update recipe metadata.

    Updates name, servings, or serving_unit. Does NOT create a new version.
    If servings changed, recalculates nutrition on the existing food.

    **Authentication required.**
    """
    try:
        recipe = await RecipeService.update_metadata(
            db=db,
            recipe_id=recipe_id,
            user_id=current_user.id,
            name=update_data.name,
            servings=update_data.servings,
            serving_unit=update_data.serving_unit,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Reload with relationships
    recipe = await _load_recipe_with_details(db, recipe.id)

    # Get per-serving nutrition
    per_serving = await _get_per_serving_nutrition(db, recipe.current_food_id)

    return _build_recipe_response(recipe, per_serving)


@router.post("/{recipe_id}/ingredients", status_code=status.HTTP_201_CREATED)
async def add_ingredient(
    recipe_id: int,
    ingredient_data: RecipeIngredientCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Add an ingredient to a recipe.

    Creates a new version of the recipe. Returns 400 if circular dependency detected.

    **Authentication required.**
    """
    # Validate food exists
    food = await db.get(Food, ingredient_data.food_id)
    if not food:
        raise HTTPException(status_code=404, detail="Food not found")

    try:
        await RecipeService.add_ingredient(
            db=db,
            recipe_id=recipe_id,
            user_id=current_user.id,
            food_id=ingredient_data.food_id,
            quantity=ingredient_data.quantity,
            unit=ingredient_data.unit,
            portion_description=ingredient_data.portion_description,
        )
    except ValueError as e:
        # Check for circular dependency error
        if "circular" in str(e).lower():
            raise HTTPException(status_code=400, detail=str(e))
        raise HTTPException(status_code=404, detail=str(e))

    return {"message": "Ingredient added successfully"}


@router.delete("/{recipe_id}/ingredients/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_ingredient(
    recipe_id: int,
    ingredient_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Remove an ingredient from a recipe.

    **Authentication required.**
    """
    # Get the recipe to check ownership
    recipe = await db.get(Recipe, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    if recipe.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get the ingredient
    ingredient = await db.get(RecipeIngredient, ingredient_id)
    if not ingredient or ingredient.recipe_id != recipe_id:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    # Delete the ingredient
    await db.delete(ingredient)
    await db.commit()

    return None


@router.get("/{recipe_id}/can-add/{food_id}", response_model=DependencyCheckResponse)
async def check_can_add_ingredient(
    recipe_id: int,
    food_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Check if a food can be added to a recipe without creating a circular dependency.

    Returns `{"allowed": true}` if the food can be added, `{"allowed": false}` otherwise.

    **Authentication required.**
    """
    # Get the recipe to check ownership
    recipe = await db.get(Recipe, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    if recipe.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get the food
    food = await db.get(Food, food_id)
    if not food:
        raise HTTPException(status_code=404, detail="Food not found")

    # Check if adding this food would create a circular dependency
    # If food_id == recipe's current_food_id, it's self-referential
    if recipe.current_food_id and food_id == recipe.current_food_id:
        return DependencyCheckResponse(allowed=False)

    # If food is a recipe-food, check for circular dependency
    if food.recipe_id is not None:
        try:
            await RecipeService._check_circular_dependency(db, recipe_id, food.recipe_id)
            return DependencyCheckResponse(allowed=True)
        except ValueError:
            # Circular dependency detected
            return DependencyCheckResponse(allowed=False)

    # Plain food, no circular dependency
    return DependencyCheckResponse(allowed=True)


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recipe(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a recipe.

    Marks the recipe's food as expired and deletes the recipe.

    **Authentication required.**
    """
    recipe = await db.get(Recipe, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    if recipe.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Mark the food as expired
    if recipe.current_food_id:
        food = await db.get(Food, recipe.current_food_id)
        if food:
            food.is_recipe_expired = True

    # Delete the recipe (cascade will delete ingredients and versions)
    await db.delete(recipe)
    await db.commit()

    return None
