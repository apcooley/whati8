# PLAN.md — Nutrition Calculator Refactor

## Goal
Eliminate redundant energy/carb coalescing layers. Make `compute_item_nutrients()` the single source of truth. Remove all nutrient_id-based lookups for energy/carbs.

## Current Architecture (3 coalescing layers — BAD)
1. `compute_item_nutrients()` → `friendly` dict (correct coalescing)
2. `compute_summary_from_precomputed()` → display_name hack to bypass `by_id`
3. `_compute_recipe_nutrients()` → two-pass global canonical ID system (60+ lines)

## Target Architecture (1 layer — GOOD)

### `compute_item_nutrients(food, qty, unit)` → `friendly` dict
- Single source of truth for per-food nutrition
- Handles all energy coalescing (Atwater General > Specific > plain)
- Handles all carb coalescing (summation > difference)
- Returns `friendly: {calories, carbs, protein, fat, fiber, sugar, sat_fat, sodium, potassium}`
- Also returns `by_id` for non-coalesced nutrients (minerals, vitamins, etc.)

### Recipe nutrition = `Σ friendly` across ingredients
```python
total_friendly = {k: 0 for k in FRIENDLY_MAP}
for ingredient in recipe.ingredients:
    friendly, _ = compute_item_nutrients(food, qty_grams, "grams")
    for k in friendly:
        total_friendly[k] += friendly[k]
```
- Store as FoodNutrient entries using canonical nutrient IDs (one mapping dict)
- No two-pass system, no energy/carb special handling
- ~15 lines instead of ~60

### Summary display = `friendly` → user config
```python
for cfg in user_config:
    if cfg.formula:
        value = eval_formula(cfg.formula, total_friendly)  # formulas ALWAYS use totals
    elif cfg.friendly_key:  # NEW: map config to friendly key
        value = total_friendly[cfg.friendly_key]
    elif cfg.nutrient_id:  # fallback for vitamins/minerals
        value = sum(by_id.get(cfg.nutrient_id, 0) for by_id in item_by_ids)
```

### Custom formulas (WW points, etc.)
- Applied to `total_friendly`, NOT per-ingredient
- Input variables are friendly keys: `Calories`, `Fat`, `Fiber`, `Protein`
- `formula_mode` simplified: formulas always get totals

## Schema Change (user_summary_nutrients)
Add `friendly_key` column (nullable):
- "Calories" → friendly_key="calories"
- "Protein" → friendly_key="protein" 
- "Carbs" → friendly_key="carbs"
- "Fat" → friendly_key="fat"
- "Fiber" → friendly_key="fiber"
- WW Points → formula (no friendly_key needed)
- Vitamin C → nutrient_id (no friendly_key)

Migration: populate `friendly_key` for existing rows based on display_name.

## Canonical Nutrient ID Mapping (for recipe FoodNutrient storage)
```python
CANONICAL_NUTRIENT_IDS = {
    "calories": 39,    # Energy
    "carbs": 81,       # Carbohydrate, by difference
    "protein": 34,     # Protein
    "fat": 80,         # Total lipid (fat)
    "fiber": 41,       # Fiber, total dietary
    "sugar": 95,       # Sugars, Total
    "sat_fat": 96,     # Fatty acids, total saturated
    "sodium": 64,      # Sodium, Na
    "potassium": 66,   # Potassium, K
}
```
These IDs should be looked up from DB on startup and cached, not hardcoded.

## Changes Required

### 1. `nutrient_calculator.py`
- `compute_item_nutrients()`: Keep as-is (already correct)
- `compute_summary_from_precomputed()`: Use `friendly_key` from config when available, fall back to `nutrient_id` for vitamins/minerals. Remove display_name hack.
- Remove `by_id` backfill (no longer needed once summary uses friendly_key)

### 2. `recipe_service.py`
- `_compute_recipe_nutrients()`: Replace 60-line two-pass system with simple `Σ friendly` loop
- Store recipe nutrition using canonical IDs from mapping
- Keep non-coalesced nutrients (vitamins/minerals) accumulated via `by_id`

### 3. `models/user_summary_nutrient.py` (or equivalent)
- Add `friendly_key: str | None` column
- Migration to populate existing rows

### 4. `summary_config.py` (router)
- `_ensure_defaults()`: Include `friendly_key` in default config creation
- API: Accept `friendly_key` in create/update

### 5. Tests
- Unit tests for simplified recipe nutrition
- Verify WW points formula uses total (not per-ingredient)
- Verify friendly_key lookup works for summary
- Verify nutrient_id fallback still works for vitamins/minerals

## Migration Plan
1. Add `friendly_key` column (nullable, no breaking change)
2. Populate `friendly_key` for existing rows
3. Update `compute_summary_from_precomputed` to prefer `friendly_key`
4. Simplify `_compute_recipe_nutrients` 
5. Remove `by_id` backfill and display_name hack
6. Update default config creation
