# PLAN.md — Refactor: Single Nutrient Calculation Path

## Goal
Replace 6+ duplicated nutrient computation paths with one function: `NutrientCalculator.compute_summary()`.
Fix the daily summary bug (missing Atwater energy coalescing).

## Tech Stack
- Backend: Python 3.11, FastAPI, SQLAlchemy (async), PostgreSQL 16
- Testing: pytest
- Linter: ruff

## Steps

### Step 1: Create NutrientCalculator + Tests
Create `whati8/services/nutrient_calculator.py` with:
- `NutrientInput` dataclass (food, quantity, unit, portions)
- `compute_summary(items, config, formula_mode)` — the one function
- Internal helpers: `_scale_nutrients()`, `_coalesce()`, `_is_energy()`, `_is_carb()`
- Name-based nutrient classification (no hardcoded IDs)
- Tests covering: coalescing, USDA vs custom scaling, portion matching, formula modes

### Step 2: Replace compute_food_summary + per-log summaries
- `DailyLogService.compute_food_summary()` → `NutrientCalculator.compute_summary()`
- Per-log `summary_nutrients` in get_daily_logs meal groups → same
- `/foods/{id}/summary` endpoint delegates to calculator

### Step 3: Replace daily totals (fix the bug)
- Daily summary in `get_daily_logs()` → `NutrientCalculator.compute_summary(all_logs, config, formula_mode="per_item")`
- Delete `nutrient_totals`, `per_log_friendly`, `friendly_values` manual computation

### Step 4: Replace recipe materialization + cleanup
- `_materialize_recipe()` → `NutrientCalculator.compute_summary(ingredients, config=[], formula_mode="total")`
- `_recalculate_nutrition()` → same
- Delete old coalesce functions, hardcoded ID constants, `_portion_scale`
