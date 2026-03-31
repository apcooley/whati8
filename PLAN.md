# PLAN.md — Fix Recipe Nutrition Calculation

## Problem
Three bugs in recipe nutrition calculation:

### Bug 1: Duplicate FoodNutrient entries
Every recipe edit creates a new materialized Food via `_materialize_recipe`, but old Food entries and their FoodNutrient rows are never cleaned up. Result: recipe food ID 19776 (Baked Potato Soup) has 6 duplicate rows for carbs, 6 for protein, etc.

### Bug 2: `_recalculate_food_nutrition` diverges from `_materialize_recipe`
When servings change, `_recalculate_food_nutrition` uses direct nutrient-per-gram math. But `_materialize_recipe` uses `compute_item_nutrients` with energy/carb coalescing. These produce different results — the recalculate path doesn't handle USDA energy variants (Atwater General vs Specific).

### Bug 3: Stale materialized foods pile up
Each recipe edit calls `_materialize_recipe` which creates a NEW Food. The old ones (with wrong macros) stay in the DB forever, consuming space and potentially showing up in searches.

## Root Cause
The recipe system has two code paths for nutrition calculation that should be one. And neither path cleans up old data.

## Fix

### Step 1: Unify nutrition calculation
- Extract the nutrition calculation from `_materialize_recipe` into a shared helper: `_compute_recipe_nutrition(db, recipe) -> (total_weight, nutrient_totals)`
- Both `_materialize_recipe` and `_recalculate_food_nutrition` call this helper
- The helper uses `compute_item_nutrients` for proper energy/carb coalescing
- Single source of truth for recipe nutrition math

### Step 2: Clean up on rematerialization
- When `_materialize_recipe` creates a new Food, delete the OLD Food's FoodNutrient and FoodPortion entries
- Mark old Food as `is_recipe_expired=True` (already exists, just not consistently set)
- `_recalculate_food_nutrition` should DELETE all existing FoodNutrient entries for the food before inserting fresh ones (prevents duplicates)

### Step 3: Data migration
- Write a one-shot script or management command that:
  1. Finds all recipes
  2. For each recipe, recalculates nutrition using the fixed code
  3. Cleans up duplicate FoodNutrient entries
  4. Cleans up stale materialized Food entries
- Run against Cloud SQL to fix existing data

### Step 4: Tests
- Test that updating servings produces correct macros (not duplicates)
- Test that editing a recipe doesn't leave duplicate FoodNutrient entries
- Test that the Baked Potato Soup specifically calculates correctly
- Test that `_compute_recipe_nutrition` matches expected values for known ingredients
