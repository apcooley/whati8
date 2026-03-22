# kJ → kcal Migration Summary

## Overview
Successfully removed all kJ→kcal conversion code from the whati8 codebase. The Energy nutrient (id=39) now stores values in kcal directly instead of kJ.

## Changes Made

### 1. Backend Python Files

#### `whati8/services/daily_log_service.py`
- Removed 6 instances of `/ 4.184` kJ→kcal conversion
- Energy values now used directly without unit checking
- Changes in:
  - Per-log calorie computation (line ~210)
  - Summary nutrient per-log computation (line ~245)
  - Ungrouped logs section (line ~290)
  - Per-log summary nutrients (line ~315)
  - Friendly values for formulas (line ~397)
  - Summary nutrient totals (line ~410)

#### `whati8/api/routers/food.py`
- Removed 2 instances of `* 4.184` kcal→kJ conversion in `create_food`
- Removed energy_nutrient lookup that checked for kJ unit
- Custom foods now store calorie values directly as provided

#### `whati8/api/routers/recipe.py`
- Removed 1 instance of `/ 4.184` kJ→kcal conversion
- Recipe nutrition now uses energy values directly

### 2. Frontend TypeScript/Svelte Files

#### `frontend/src/lib/types/profile.ts`
- Removed kJ unit check in `getFoodCalPerGram` function
- Energy values now used directly without conversion

#### `frontend/src/lib/components/EditLogSheet.svelte`
- Removed kJ unit check when calculating calories per gram
- Simplified energy value handling

### 3. Import Script

#### `scripts/import_usda_data.py`
- **UPDATED**: Changed logic to store kcal instead of kJ
- Now converts kJ→kcal when importing USDA nutrient 1062
- Uses kcal directly when importing USDA nutrient 1008
- Prefers kcal (1008) over kJ (1062) when both present

### 4. Migration Script

#### `scripts/migrate_energy_to_kcal.py` (NEW)
- Created data migration script to update production database
- Steps performed:
  1. Changes Energy nutrient (id=39) unit from 'kJ' to 'kcal'
  2. Converts custom food energy values from kJ back to kcal (÷ 4.184)
  3. Warns about USDA foods needing re-import
- **DO NOT RUN** until ready to migrate production database
- Safe to run: checks current unit before applying changes

## Verification

### All Migration Tests Pass ✅
```bash
uv run python -m pytest tests/test_kcal_migration.py -v
# 10 passed
```

Tests verify:
- Energy nutrient unit is kcal
- Custom food creation stores kcal directly
- Daily log calories are correct for USDA and custom foods
- Gram-based logging works correctly
- NO instances of `4.184` in production code
- Recipe materialization uses kcal

### All Existing Tests Pass ✅
```bash
uv run python -m pytest tests/test_calorie_chain.py tests/test_photo_food_creation.py \
  tests/test_recipe_service.py tests/test_recipe_api.py -v
# 52 passed
```

### Frontend Builds Successfully ✅
```bash
cd frontend && npx vite build
# ✓ built in 1.41s
```

### No Stray Conversions ✅
```bash
grep -rn "4.184" whati8/ frontend/src/ scripts/ --include="*.py" --include="*.ts" --include="*.svelte" | grep -v test | grep -v __pycache__
```

Results:
- `scripts/migrate_energy_to_kcal.py` - Migration script (expected)
- `scripts/import_usda_data.py` - kJ→kcal conversion for imports (expected)

## Migration Path for Production

### Phase 1: Code Deployment (DONE)
- ✅ All conversion code removed
- ✅ Tests passing
- ✅ Frontend building

### Phase 2: Database Migration (TODO)
1. **Backup database** before running migration
2. Run migration script:
   ```bash
   uv run python scripts/migrate_energy_to_kcal.py
   ```
3. Verify custom foods show correct calorie values
4. Note: USDA foods will show incorrect values until re-import

### Phase 3: USDA Re-import (TODO)
1. Re-run USDA import script to update all food values:
   ```bash
   uv run python scripts/import_usda_data.py
   ```
2. Import script now converts kJ→kcal automatically
3. All USDA foods will have correct kcal values

### Phase 4: Verification (TODO)
1. Spot-check several foods in the UI
2. Verify daily logs show correct calorie totals
3. Check recipe nutrition calculations
4. Run full test suite in production environment

## Notes

- **Backward Compatibility**: None. This is a breaking change requiring data migration.
- **API Changes**: None. All API endpoints continue to work as before.
- **Frontend Changes**: Transparent to users. UI displays kcal as it always has.
- **Performance**: No impact. Removed conversion overhead improves performance slightly.

## Files Changed

### Modified
- `whati8/services/daily_log_service.py`
- `whati8/api/routers/food.py`
- `whati8/api/routers/recipe.py`
- `frontend/src/lib/types/profile.ts`
- `frontend/src/lib/components/EditLogSheet.svelte`
- `scripts/import_usda_data.py`

### Created
- `scripts/migrate_energy_to_kcal.py`

### Not Modified (Test Files)
- All test files remain unchanged
- Tests verify correct behavior with new kcal storage
