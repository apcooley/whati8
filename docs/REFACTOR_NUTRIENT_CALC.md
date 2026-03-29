# Refactor Plan: Single Nutrient Calculation Path

## Problem

Nutrient computation is duplicated 6+ times. Each copy has different bugs.
Daily summary doesn't coalesce energy. Recipe materialization had hardcoded IDs.

## Solution: One function

```python
NutrientCalculator.compute_summary(
    items: list[NutrientInput],        # food + quantity + unit
    config: list[UserSummaryNutrient], # user's display preferences
    level: str = "item",               # "item" | "recipe" | "day"
    servings: float = 1,               # recipe only: divide totals
) -> list[dict]
```

### What `level` controls

| Level | Input | Formula behavior | Division |
|-------|-------|-----------------|----------|
| `item` | 1 food | Apply once to total | None |
| `recipe` | N ingredients | Apply once to total | ÷ servings |
| `day` | N food logs | Apply per-item, sum results | None |

Everything else is identical: scale → coalesce → map to friendly names → evaluate config.

### `NutrientInput` dataclass

```python
@dataclass
class NutrientInput:
    food: Food                    # has food_nutrients, serving_size, created_by_user_id
    quantity: float
    unit: str
    portions: list[FoodPortion]   # for portion matching
```

Built from a `FoodLog`, a `RecipeIngredient`, or a direct food lookup.

### Internal pipeline (all in one function)

```
items → [scale each] → [coalesce energy/carbs per item] → [aggregate]
      → [map to friendly names] → [apply formulas per level] → [format per config]
```

### Name-based classification (no hardcoded IDs)

```python
def _is_energy(name: str) -> bool:
    return name.lower().startswith("energy") or "atwater" in name.lower()

def _is_carb(name: str) -> bool:
    return "carbohydrate" in name.lower()
```

### Callers (all replaced)

| Current code | Becomes |
|-------------|---------|
| `compute_food_summary()` | `compute_summary(items=[food], config=config, level="item")` |
| Per-log summary in meal groups | `compute_summary(items=[log], config=config, level="item")` |
| Daily totals (BUGGY) | `compute_summary(items=all_logs, config=config, level="day")` |
| Recipe materialization | `compute_summary(items=ingredients, config=config, level="recipe", servings=N)` |
| Recipe cascade recalc | Same as above |

### Steps

1. **Create `nutrient_calculator.py`** with `NutrientCalculator.compute_summary()` + helpers
2. **Write tests** (`test_nutrient_calculator.py`) — coalescing, scaling, levels, formulas
3. **Replace all 6 callers** one commit at a time
4. **Delete dead code** — old coalesce functions, constants, duplicated logic

### What doesn't change
- Database schema
- API response shapes
- Frontend
- User behavior (except: daily totals will be correct)

### Estimate
- ~200 lines new (calculator + dataclass)
- ~400 lines deleted
- 4 commits
