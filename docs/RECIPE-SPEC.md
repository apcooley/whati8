# Recipe System — Technical Specification

## Overview

Recipes are user-created composite foods built from individual ingredients (foods or other recipes). When a recipe is created or updated, it materializes as a food entry in the `foods` table with auto-calculated nutrition. Recipes support versioning: editing ingredients creates a new version while preserving old versions for historical log accuracy.

## Data Model

### Existing Tables (no changes)
- `foods` — recipe versions materialize here as custom foods
- `food_nutrients` — computed per-serving nutrition for materialized recipe foods
- `food_portions` — portions for recipe foods (serving unit + grams/oz)
- `user_foods` — user's profile food linking to the current recipe version's food entry
- `food_logs` — logs reference a specific food_id (= specific recipe version)

### Schema Changes to `recipes`

```sql
ALTER TABLE recipes ADD COLUMN servings NUMERIC(10,2) NOT NULL DEFAULT 1;
ALTER TABLE recipes ADD COLUMN serving_unit VARCHAR(50) NOT NULL DEFAULT 'serving';
ALTER TABLE recipes ADD COLUMN current_version INT NOT NULL DEFAULT 1;
ALTER TABLE recipes ADD COLUMN current_food_id INT REFERENCES foods(id);
-- current_food_id points to the latest materialized food entry
```

New columns:
| Column | Type | Description |
|--------|------|-------------|
| `servings` | NUMERIC(10,2) | Number of servings the recipe makes (e.g. 8) |
| `serving_unit` | VARCHAR(50) | Name for one serving (e.g. "serving", "slice", "cookie") |
| `current_version` | INT | Current version number, incremented on ingredient changes |
| `current_food_id` | INT FK→foods | Points to the latest materialized food entry |

### New Table: `recipe_versions`

```sql
CREATE TABLE recipe_versions (
    id SERIAL PRIMARY KEY,
    recipe_id INT NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    version INT NOT NULL,
    food_id INT NOT NULL REFERENCES foods(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(recipe_id, version)
);
```

Tracks the food_id for each version. When a recipe is edited:
1. Increment `recipes.current_version`
2. Materialize new food entry in `foods`
3. Insert into `recipe_versions`
4. Update `recipes.current_food_id`
5. Mark old food entry: set `notes = 'recipe_expired:v{N}'` (or a boolean column) so it's excluded from searches but still valid for existing logs

### Changes to `recipe_ingredients`

```sql
ALTER TABLE recipe_ingredients ADD COLUMN portion_description VARCHAR(200);
-- portion_description stores the selected portion label, e.g. "cup (125g)"
-- unit column continues to store the base unit name
-- food_id can reference a recipe's materialized food (enabling nesting)
```

### Changes to `foods`

```sql
ALTER TABLE foods ADD COLUMN recipe_id INT REFERENCES recipes(id);
ALTER TABLE foods ADD COLUMN recipe_version INT;
ALTER TABLE foods ADD COLUMN is_recipe_expired BOOLEAN NOT NULL DEFAULT FALSE;
```

New columns:
| Column | Type | Description |
|--------|------|-------------|
| `recipe_id` | INT FK→recipes | If this food was materialized from a recipe |
| `recipe_version` | INT | Which version of the recipe this food represents |
| `is_recipe_expired` | BOOLEAN | True for old versions; excluded from searches |

## Nutrition Calculation

### Per-Ingredient Nutrition
For each ingredient in a recipe:
1. Look up the food's `food_nutrients` (amount_per_serving values)
2. Determine the gram weight: `quantity × portion.gram_weight`
3. Compute base:
   - USDA food: `base = 100` (nutrients are per 100g)
   - Custom food: `base = food.serving_size` (nutrients are per serving)
4. Scale: `nutrient_value = amount_per_serving × (gram_weight / base)`

### Recipe Total → Per-Serving
1. Sum all ingredient nutrients → recipe total
2. Divide by `recipe.servings` → per-serving nutrition
3. Store per-serving values in `food_nutrients` for the materialized food
4. Total recipe weight = sum of all ingredient gram weights
5. Per-serving weight = total_weight / servings → stored as `food.serving_size`

### Nested Recipes
When a recipe includes another recipe as an ingredient:
- The ingredient's `food_id` points to the nested recipe's `current_food_id`
- Nutrition lookup is the same as any other food (just read its food_nutrients)
- No special handling needed at calculation time

### Circular Dependency Prevention
Before allowing an ingredient to be added:
1. If the ingredient's food has `recipe_id IS NOT NULL`, it's a recipe-food
2. Walk the dependency chain: recipe → ingredients → any that are recipe-foods → their recipe → ingredients → ...
3. If the current recipe's ID appears anywhere in the chain → **reject** (circular dependency)

Algorithm (recursive):
```python
def get_recipe_dependencies(recipe_id: int, db) -> set[int]:
    """Return all recipe IDs that this recipe depends on (transitively)."""
    deps = set()
    ingredients = get_ingredients(recipe_id)
    for ing in ingredients:
        food = get_food(ing.food_id)
        if food.recipe_id and food.recipe_id not in deps:
            deps.add(food.recipe_id)
            deps |= get_recipe_dependencies(food.recipe_id, db)
    return deps

# Before adding ingredient with food_id:
food = get_food(food_id)
if food.recipe_id:
    deps = get_recipe_dependencies(food.recipe_id, db)
    if current_recipe_id in deps or food.recipe_id == current_recipe_id:
        raise ValueError("Circular dependency detected")
```

## Versioning Flow

### On Recipe Create
1. Create `recipes` row (servings, serving_unit, name, current_version=1)
2. Create `recipe_ingredients` rows
3. Calculate nutrition (sum ingredients → divide by servings)
4. Create `foods` row (name=recipe.name, serving_size=weight_per_serving, unit='g', recipe_id, recipe_version=1, created_by_user_id)
5. Create `food_nutrients` rows (per-serving values, converting kcal→kJ for Energy)
6. Create `food_portions` rows (serving unit + grams + oz)
7. Insert `recipe_versions` (version=1, food_id)
8. Set `recipes.current_food_id`
9. Auto-register in `user_foods` (default_unit=serving_unit, default_quantity=1)

### On Recipe Edit (ingredient changes)
1. Increment `recipes.current_version`
2. Mark old food: `foods.is_recipe_expired = TRUE` where `food_id = old current_food_id`
3. Create NEW `foods` row with same name, new nutrition
4. Create new `food_nutrients`, `food_portions`
5. Insert `recipe_versions` (new version, new food_id)
6. Update `recipes.current_food_id = new food_id`
7. Update `user_foods.food_id = new food_id` (point profile food to latest version)
8. **Cascade**: Find all recipes that use this recipe as an ingredient → recursively re-materialize them too (new version for each)

### On Recipe Edit (name/servings only)
1. Update `recipes.name`, `recipes.servings`, `recipes.serving_unit` in place
2. Recalculate per-serving nutrition (same ingredients, different divisor)
3. Update existing food entry in place (no new version — `food.name`, `food.serving_size`, nutrient values)
4. **Cascade**: If servings changed, per-serving nutrition changed → cascade to parent recipes

### Cascade Algorithm
```python
async def cascade_recipe_update(recipe_id: int, db):
    """Find and re-materialize all recipes that depend on this one."""
    # Find recipes whose ingredients include foods materialized from this recipe
    parent_recipes = await db.execute(
        select(RecipeIngredient.recipe_id)
        .join(Food, RecipeIngredient.food_id == Food.id)
        .where(Food.recipe_id == recipe_id)
        .distinct()
    )
    for (parent_id,) in parent_recipes:
        await rematerialize_recipe(parent_id, db)
        await cascade_recipe_update(parent_id, db)  # recursive
```

## API Endpoints

### Recipe CRUD
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/recipes/` | Create recipe with ingredients |
| `GET` | `/recipes/` | List user's recipes |
| `GET` | `/recipes/{id}` | Get recipe with ingredients |
| `PUT` | `/recipes/{id}` | Update recipe (name/servings/ingredients) |
| `DELETE` | `/recipes/{id}` | Delete recipe (marks food expired, keeps logs) |

### Recipe Ingredients
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/recipes/{id}/ingredients` | Add ingredient |
| `PUT` | `/recipes/{id}/ingredients/{ing_id}` | Update ingredient qty/unit |
| `DELETE` | `/recipes/{id}/ingredients/{ing_id}` | Remove ingredient |

### Recipe Photo
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/recipes/recognize` | Photo → parsed ingredient lines (text only, no matching) |

### Dependency Check
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/recipes/{id}/can-add/{food_id}` | Check if food can be added (no circular dep) |

## Request/Response Schemas

### Create Recipe
```json
POST /recipes/
{
  "name": "Mom's Chili",
  "servings": 8,
  "serving_unit": "bowl",
  "ingredients": [
    { "food_id": 1234, "quantity": 2, "unit": "cup", "portion_description": "cup (240g)" },
    { "food_id": 5678, "quantity": 1, "unit": "lb", "portion_description": "lb (454g)" }
  ]
}
```

### Recipe Response
```json
{
  "id": 1,
  "name": "Mom's Chili",
  "servings": 8,
  "serving_unit": "bowl",
  "current_version": 1,
  "food_id": 9001,
  "ingredients": [
    {
      "id": 1,
      "food_id": 1234,
      "food_name": "Kidney Beans, canned",
      "quantity": 2,
      "unit": "cup",
      "portion_description": "cup (240g)",
      "calories": 450,
      "state": "locked"
    }
  ],
  "per_serving": {
    "weight_g": 300,
    "calories": 285,
    "protein_g": 22,
    "carbs_g": 30,
    "fat_g": 8,
    "fiber_g": 10
  },
  "total": {
    "weight_g": 2400,
    "calories": 2280
  }
}
```

### Photo Recognize (Recipe)
```json
POST /recipes/recognize  (multipart: file)

Response:
{
  "lines": [
    "2 cans kidney beans",
    "1 lb ground turkey",
    "1 large onion, diced",
    "2 tbsp chili powder"
  ]
}
```
Returns raw text lines only. No DB matching. Frontend displays each line in editing mode for user to match.

## Frontend Components

### RecipeBuilder (new)
Full-page recipe creation/editing view.

**Header section:**
- Recipe name (text input)
- Servings count (number input) + serving unit name (text input, default "serving")

**Ingredients list:**
Each row has two states:

**Editing state:**
- Text input with typeahead search (searches user_foods first, then USDA)
- "+" button → navigates to Add Food flow, returns with selected food
- Quantity input + unit dropdown (populated from food's portions once matched)
- Once food matched + quantity set → "Lock" button (checkmark)

**Locked state:**
- Shows: food name, quantity, unit, per-ingredient calories
- "Edit" button (pencil icon) → unlocks back to editing
- "Remove" button (trash icon)

**Footer section:**
- Per-serving nutrition summary (live-calculated as ingredients are added)
- "Save Recipe" button → creates recipe + materializes food
- "📷 Scan Recipe" button → photo flow, prepopulates lines in editing mode

### RecipeList (in Log tab or Add tab)
- Shows user's recipes with per-serving nutrition
- Tap to log (same as any food) or long-press/edit button to edit recipe

### Integration Points
- Add tab: "Create Recipe" button alongside USDA Search, Take Photo, Enter Manually
- Log tab: recipes appear in "Your Foods" (they ARE foods)
- Today tab: recipe logs show like any other food log
- Edit food: if food has `recipe_id`, show "Edit Recipe" link

## Edge Cases & Tests Required

### Circular Dependencies
1. Recipe A has ingredient Food 1 → add Food 1 to A: OK (not a recipe)
2. Recipe A materializes as Food A → add Food A to Recipe A: **REJECT**
3. Recipe A → Recipe B (as ingredient) → try to add Recipe A to B: **REJECT**
4. A→B→C → try to add C to A: **REJECT** (transitive)
5. A→B, C→D → add D to A: OK (no cycle)
6. Deep chain: A→B→C→D→E → add E to A: **REJECT**

### Versioning
1. Create recipe v1 → log it → edit recipe → v2 created → old log still shows v1 nutrition
2. Edit name only → no new version, food updated in place
3. Edit servings only → no new version, food updated in place (nutrition recalculated)
4. Add ingredient → new version
5. Remove ingredient → new version
6. Change ingredient quantity → new version
7. Old version food has `is_recipe_expired=TRUE`, excluded from search
8. Old version food still valid for `food_logs` FK

### Cascading Updates
1. Recipe A uses Recipe B → edit B → A auto-gets new version too
2. A→B→C → edit C → B gets new version → A gets new version
3. Cascade respects circular dependency prevention (can't happen if deps are valid)

### Nutrition Accuracy
1. Recipe with 2 USDA ingredients → nutrition = sum of scaled USDA values
2. Recipe with 1 custom + 1 USDA ingredient → mixed base (custom per serving_size, USDA per 100g)
3. Recipe with nested recipe → nested recipe's per-serving nutrition scaled correctly
4. Servings=1 → per-serving = total
5. Change servings 4→8 → per-serving halves

### Photo Flow
1. Photo returns text lines → each displayed in editing mode
2. User can match each line to a food
3. Unmatched lines stay in editing mode
4. User can add new food from within recipe builder
5. Save blocked until all lines are matched or deleted (show "X ingredients not matched" warning)

## Migration Plan

1. Alembic migration: add columns to `recipes`, `foods`; create `recipe_versions` table
2. Backend: Recipe service (CRUD + materialization + cascade + dependency check)
3. Backend: Recipe API router
4. Backend: Tests (circular deps, versioning, cascade, nutrition accuracy)
5. Frontend: RecipeBuilder component
6. Frontend: Integration into Add tab + Log tab
7. Frontend: Photo recipe flow
