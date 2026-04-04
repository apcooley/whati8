---
date: 2026-03-31
status: draft
author: Aaron Cooley
---

# Requirements: Phase 1 — USDA Sanitization

## Problem Statement

whati8 stores nutrient data from USDA FoodData Central in a `food_nutrients` junction table with `amount_per_serving` values that are **always per 100g** for USDA foods, regardless of the `foods.serving_size` field. Energy and carbohydrate data exists in multiple USDA variants (plain Energy, Atwater General, Atwater Specific; Carbohydrate by difference vs. by summation). The app currently coalesces these variants at runtime in 3 separate code paths, each with its own bugs.

Phase 1 eliminates the need for runtime coalescing by pre-computing the 5 core macros into denormalized columns on the `foods` table, along with metadata columns (`tier`, `data_source`, `is_deprecated`, `is_complete`, `sanitized_base_grams`).

Additionally, the Foundation Foods import was incomplete (~265 of ~1000 foods imported). Phase 1 re-imports the full Foundation dataset before sanitization.

## Goals

- Add `sanitized_calories`, `sanitized_protein`, `sanitized_carbs`, `sanitized_fat`, `sanitized_fiber` columns to `foods` table, populated for ALL foods
- Add `sanitized_base_grams` column — the gram amount that sanitized values are relative to
- Add `tier`, `data_source`, `is_deprecated`, `is_complete`, `imported_at` columns to `foods` table
- Re-import Foundation Foods dataset to fill the gap (265 → ~1000)
- Verify sanitized values match existing runtime calculation for all foods (<1% variance)
- Zero NULL `sanitized_calories` for any USDA food after sanitization

## Non-Goals

- Changing the runtime calculation to use sanitized columns (Phase 2b)
- Modifying `user_foods` / pantry (Phase 2a)
- Changing search ranking (Phase 2c)
- Frontend changes
- Actually using the `is_deprecated` column to hide or de-prioritize foods (future)
- Cleaning up test data (`TEST_CALC_FIX_*`, `TEST_MIXED_ENERGY_*` entries)

## Functional Requirements

### Schema Changes (Alembic migration)

1. Add the following columns to `foods`:

   | Column | Type | Default | Nullable | Description |
   |--------|------|---------|----------|-------------|
   | `tier` | `SMALLINT` | — | Yes | 0=USDA, 1=curated, 10=custom, 20=recipe |
   | `data_source` | `VARCHAR(50)` | — | Yes | `foundation`, `sr_legacy`, `custom`, `recipe` |
   | `is_deprecated` | `BOOLEAN` | `false` | No | Marks foods that should eventually be hidden |
   | `imported_at` | `TIMESTAMP` | — | Yes | When this food was imported/created |
   | `is_complete` | `BOOLEAN` | `true` | No | Has all 5 core macros (cal/protein/carb/fat/fiber) |
   | `sanitized_base_grams` | `DECIMAL(10,2)` | — | Yes | Gram amount sanitized values are relative to |
   | `sanitized_calories` | `DECIMAL(10,2)` | — | Yes | Pre-coalesced kcal per `sanitized_base_grams` |
   | `sanitized_protein` | `DECIMAL(10,2)` | — | Yes | Grams per `sanitized_base_grams` |
   | `sanitized_carbs` | `DECIMAL(10,2)` | — | Yes | Grams per `sanitized_base_grams` |
   | `sanitized_fat` | `DECIMAL(10,2)` | — | Yes | Grams per `sanitized_base_grams` |
   | `sanitized_fiber` | `DECIMAL(10,2)` | — | Yes | Grams per `sanitized_base_grams` |

2. Add index on `tier`: `CREATE INDEX ix_foods_tier ON foods (tier)`
3. Add index on `data_source`: `CREATE INDEX ix_foods_data_source ON foods (data_source)`
4. Migration must be backward-compatible: all new columns are nullable or have defaults. No existing columns modified or removed.

### Foundation Foods Re-Import

5. Download the latest Foundation Foods dataset from USDA FDC (JSON format).
6. Import all Foundation Foods, deduplicating against existing foods by `usda_fdc_id`.
7. For foods that already exist (matching `usda_fdc_id`): update nutrient data if the new dataset has more/different nutrients. Do NOT delete existing foods.
8. For new Foundation foods: insert as normal with all nutrients and portions.
9. Run the existing dedup logic: when a Foundation food and SR Legacy food share the same name, keep the Foundation food (higher FDC ID).
10. Log import stats: foods created, foods updated, duplicates removed.

### Sanitization Script (`scripts/sanitize_foods.py`)

11. Script runs independently after Alembic migration. Idempotent (safe to re-run).
12. Connects to the database directly (no FastAPI required). Accepts `--database-url` or reads from environment.

#### USDA Foods (tier=0)

13. Set `tier = 0` for all foods where `usda_fdc_id IS NOT NULL`.
14. Set `data_source`:
    - `foundation` if `usda_fdc_id >= 300000` OR food has any `Energy (Atwater General Factors)` or `Energy (Atwater Specific Factors)` nutrient
    - `sr_legacy` otherwise
15. Set `sanitized_base_grams = 100` for all USDA foods. (USDA `food_nutrients.amount_per_serving` values are always per 100g, regardless of `foods.serving_size`.)
16. Energy coalescing priority: pick the best available energy value from `food_nutrients`:
    - Priority 1: `Energy (Atwater General Factors)` (nutrient name exact match)
    - Priority 2: `Energy (Atwater Specific Factors)` (nutrient name exact match)
    - Priority 3: `Energy` (nutrient name exact match, kcal)
    - All energy values in `food_nutrients` are already in kcal (the import script converts kJ → kcal at import time, confirmed in `parse_food_item`)
    - Store result in `sanitized_calories`
17. Carbohydrate coalescing priority:
    - Priority 1: `Carbohydrate, by summation`
    - Priority 2: `Carbohydrate, by difference`
    - Store result in `sanitized_carbs`
18. Direct copy (no coalescing needed):
    - `Protein` → `sanitized_protein`
    - `Total lipid (fat)` → `sanitized_fat`
    - `Fiber, total dietary` → `sanitized_fiber`
19. Set `is_complete = false` if any of `sanitized_calories`, `sanitized_protein`, `sanitized_carbs`, `sanitized_fat` is NULL after coalescing. (Missing fiber is OK — `is_complete` remains true.)
20. Set `imported_at = NOW()` for all USDA foods (or `created_at` if available and more accurate).
21. Set `is_deprecated = false` for all USDA foods (column exists but not used yet).

#### Custom Foods (tier=10)

22. Set `tier = 10` for foods where `created_by_user_id IS NOT NULL AND recipe_id IS NULL`.
23. Set `data_source = 'custom'`.
24. Set `sanitized_base_grams` from `food_portions` gram weight lookup:
    - If `foods.unit` is a gram variant (`g`, `gram`, `grams`): `sanitized_base_grams = foods.serving_size`
    - If `foods.unit` is a mass unit (`oz`, `lb`, `kg`): convert to grams using standard conversions (oz=28.3495g, lb=453.592g, kg=1000g), multiply by `foods.serving_size`
    - If `foods.unit` is a volume unit (`cup`, `tbsp`, `tsp`, `ml`, `fl oz`): look up the food's portion with matching unit_name to get `gram_weight`, use `gram_weight * (serving_size / portion.amount)`. If no matching portion, use water density as default (1 ml = 1g).
    - If `foods.unit` is a custom unit (`bar`, `bottle`, `slice`, etc.): look up the food's portion with matching `unit_name` to get `gram_weight`. Use `gram_weight * (serving_size / portion.amount)`. If no matching portion found, assume `serving_size` grams and mark for review.
25. Copy the 5 core macros directly from `food_nutrients`:
    - `Energy` → `sanitized_calories`
    - `Protein` → `sanitized_protein`
    - `Carbohydrate, by difference` → `sanitized_carbs`
    - `Total lipid (fat)` → `sanitized_fat`
    - `Fiber, total dietary` → `sanitized_fiber`
    - Custom foods always use the nutrient name `Energy` (never Atwater variants). No coalescing needed.
26. Set `is_complete` using the same rule as USDA (missing cal/protein/carb/fat → incomplete).

#### Recipe Foods (tier=20)

27. Set `tier = 20` for foods where `recipe_id IS NOT NULL`.
28. Set `data_source = 'recipe'`.
29. Set `sanitized_base_grams = foods.serving_size` (recipe foods have gram-based serving sizes).
30. Compute sanitized macros by summing across the recipe's ingredients:
    - For each `RecipeIngredient`: look up ingredient food's `sanitized_*` values, scale by `(quantity_in_grams / ingredient.food.sanitized_base_grams)`, sum.
    - Divide total by `recipe.servings` to get per-serving values.
    - Store in `sanitized_calories/protein/carbs/fat/fiber`.
    - **Dependency:** Recipe food sanitization runs AFTER USDA and custom food sanitization (ingredients must already have sanitized values).
31. Only sanitize the **current** recipe food (`recipe.current_food_id`). Skip expired recipe foods (`is_recipe_expired = true`).

### Verification

32. After sanitization, run a full-population comparison:
    - For every food, compute macros using the existing runtime `compute_item_nutrients()` function (1 serving).
    - Compare against `sanitized_*` values scaled to 1 serving: `sanitized_X * (serving_size / sanitized_base_grams)` — wait, this isn't right for USDA where serving_size ≠ 100g. Instead, compare at the per-100g level for USDA foods, and per-serving for custom foods.
    - Actually: compare `sanitized_*` directly against the `food_nutrients.amount_per_serving` source values (which are per-100g for USDA, per-serving for custom). The sanitized values should match within rounding (no variance allowed — they're copies).
33. Flag any food where sanitized value differs from source by >0.01 (rounding tolerance).
34. Verify: `SELECT COUNT(*) FROM foods WHERE sanitized_calories IS NULL AND usda_fdc_id IS NOT NULL` = 0.
35. Verify: `SELECT COUNT(*) FROM foods WHERE is_complete = false AND usda_fdc_id IS NOT NULL` — report count, expected to be small (kJ-edge-cases or truly incomplete USDA entries).
36. Print summary stats: foods sanitized by type (USDA/custom/recipe), incomplete count, verification pass/fail count.

## Non-Functional Requirements

- **Idempotency**: Sanitization script can be run multiple times safely. Uses UPDATE (not INSERT) for sanitized columns.
- **Performance**: Script should complete in <60 seconds for ~8000 foods on local DB.
- **No downtime**: Alembic migration adds nullable columns only. No table locks beyond standard ALTER TABLE.
- **No runtime changes**: This phase does NOT change any API endpoint behavior. Sanitized columns exist but are not yet read by the application.

## Constraints & Assumptions

- USDA `food_nutrients.amount_per_serving` is always per 100g for USDA foods, regardless of `foods.serving_size`. Confirmed by inspecting import script and spot-checking known foods.
- The import script converts kJ → kcal during import (`amount / 4.184`), so all energy values in `food_nutrients` are in kcal.
- Custom foods have 5 core nutrients stored in `food_nutrients` with names `Energy`, `Protein`, `Carbohydrate, by difference`, `Total lipid (fat)`, `Fiber, total dietary`.
- Custom foods with non-gram units (bar, bottle, slice, etc.) have a corresponding `food_portions` entry with `gram_weight` for that unit.
- Foundation Foods identified by: `usda_fdc_id >= 300000` OR presence of Atwater energy variants. SR Legacy is everything else.
- Foundation dataset (~1000 foods) was only partially imported (~265). Re-import needed.
- The `food_nutrients` table is not modified by this phase. It remains the source of truth for all nutrients including vitamins/minerals.

## Execution Order

1. Run Alembic migration (add columns)
2. Re-import Foundation Foods (download + import + dedup)
3. Run sanitization script on local DB
4. Run verification on local DB
5. Run sanitization on staging DB
6. Run verification on staging DB
7. Aaron approves → run on prod DB

## Open Questions

*None — all resolved during requirements gathering.*

## References

- [PLAN-nutrition-refactor.md](/home/aaron/source/whati8/docs/PLAN-nutrition-refactor.md) — Master refactor plan
- [USDA FDC Bulk Downloads](https://fdc.nal.usda.gov/download-datasets/)
- [Import script](/home/aaron/source/whati8/scripts/import_usda_data.py) — Current USDA import logic
- [Nutrient calculator](/home/aaron/source/whati8/whati8/services/nutrient_calculator.py) — Current runtime coalescing
- [Recipe service](/home/aaron/source/whati8/whati8/services/recipe_service.py) — Recipe nutrition calculation
- Nutrient IDs: 39=Energy, 199=Energy (Atwater General), 200=Energy (Atwater Specific), 81=Carb by difference, 107=Carb by summation, 34=Protein, 80=Fat, 41=Fiber
