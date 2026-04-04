# whati8 Nutrition Refactor — Phased Plan

**Date:** 2026-03-31  
**Authors:** Aaron Cooley, Barney (AI assistant)  
**Status:** Draft v2 (incorporating architecture review feedback)

---

## 1. Context

### What whati8 is
A personal nutrition tracking web app (FastAPI + SvelteKit + PostgreSQL) deployed on GCP Cloud Run. Users log food, build recipes, and track macros against Weight Watchers points and custom goals.

### Current Data Model

**foods** — Single table for all food items
- 7,985 USDA foods (imported from USDA FoodData Central)
- 104 custom user-created foods (manual entry)
- 14 materialized recipe foods (auto-generated when recipes are created/edited)
- Differentiated by: `usda_fdc_id` (USDA) vs `created_by_user_id` (custom) vs `recipe_id` (recipe)

**nutrients** — 244 nutrient definitions
- Includes multiple energy variants: `Energy` (7,921 foods), `Energy (Atwater General Factors)` (144 foods), `Energy (Atwater Specific Factors)` (139 foods)
- Includes multiple carb variants: `Carbohydrate, by difference` (8,052 foods), `Carbohydrate, by summation` (33 foods)

**food_nutrients** — 643,854 junction rows (food × nutrient × amount_per_serving)
- For USDA foods: `amount_per_serving` is per 100g
- For custom foods: `amount_per_serving` is per `food.serving_size`
- No pre-coalesced values; energy/carb coalescing happens at runtime in 3 separate places

**food_portions** — 14,753 portion definitions
- USDA-sourced: inconsistent quality ("undetermined" units, duplicate measures)
- Custom foods: user-defined portions

**user_foods** — 114 entries (user's registered food library)
- Links user to food with personalized defaults (nickname, default_qty, default_unit)
- Usage tracking (use_count, last_used_at, is_favorite)

**recipes** — 12 recipes with RecipeIngredient → Food links
- Recipes materialize as Food entries with computed FoodNutrient rows
- Versioned: each edit creates new Food, old marked `is_recipe_expired=true`

**user_summary_nutrients** — 9 config rows
- Per-user display config for nutrition summary (which nutrients to show, in what order)
- Supports custom formulas (e.g., WW points: `round(Calories/50+Fat/12-min(Fiber,4)/5,1)`)
- Currently references nutrients by `nutrient_id` — breaks when food uses a different energy variant

**Nutrient calculation pipeline (current — 3 coalescing sites):**
1. `compute_item_nutrients(food, qty, unit)` → `friendly` dict + `by_id` dict
2. `NutrientCalculator.compute_summary()` → applies user config to friendly/by_id
3. `RecipeService._compute_recipe_nutrients()` → sums across ingredients using two-pass global canonical ID system

---

## 2. Problem Statement

### P1: Runtime energy/carb coalescing is fragile and buggy
USDA foods store energy in different nutrient variants (plain Energy, Atwater General, Atwater Specific). The app must coalesce at runtime in **three separate places**. Each implementation has had bugs:
- Recipe nutrition showed 73 cal instead of 106 cal (global canonical ID dropped ingredients with different energy variants)
- Summary endpoint showed 0 cal for USDA foods with only Atwater energy
- Workaround patches (by_id backfill, display_name matching) add complexity without fixing root cause

### P2: No data quality tiers
All 7,985 USDA foods are treated equally. Well-documented "Chicken, breast, raw" sits next to "Babyfood, plums, strained" with incomplete data. Search results flood the user with irrelevant options. No way to distinguish trusted data from questionable data.

### P3: User's food library is disconnected from recipe workflow
`user_foods` (registered foods) and recipe ingredients operate independently. A user can add an unregistered USDA food (with potentially bad data) directly to a recipe. No inline macro preview during recipe building. No confirmation flow.

### P4: Recipe nutrition is invisible during building
User adds 8 ingredients to a recipe, saves, then discovers the macros are wrong. No per-ingredient calorie/protein/carb/fat preview during the build process.

### P5: Portion data is inconsistent
USDA portions include "undetermined" units, duplicate measures, and inconsistent naming. No standardization.

---

## 3. Solution: Food Tier System + Pantry + Sanitized Import

### 3.1 Core Concepts

**Food Tiers** (global, on `foods` table):
| Tier | Badge | Label   | Source                                                                  |
|------|-------|---------|-------------------------------------------------------------------------|
| 0    | 🔴    | USDA    | Sanitized USDA import. Pre-coalesced macros. Complete data.             |
| 1    | 🟡    | Curated | Admin-curated common foods. AI-generated rules pick canonical variants. |
| 10   | —     | Custom  | User-created foods (manual entry).                                      |
| 20   | —     | Recipe  | Materialized recipe foods (auto-generated).                             |

**Pantry** (per-user, extends existing `user_foods` table):
- "Green" 🟢 = food is in this user's pantry (any tier)
- Stores: default_qty, default_unit, nickname, favorites
- Persistent: soft-deleted on remove via `removed_at` (preserves preferences for re-add)
- Stores `source_tier` (immutable) — original tier at time of add, for demotion on remove
- Auto-promoted: logging a food or adding to recipe auto-adds to pantry

**Sanitized macros** (on `foods` table):
- `sanitized_calories`, `sanitized_protein`, `sanitized_carbs`, `sanitized_fat`, `sanitized_fiber`
- `sanitized_base_grams` — the gram amount that sanitized values are relative to
  - USDA foods: 100 (nutrients are per 100g)
  - Custom foods: gram-equivalent of their serving size
  - Recipe foods: computed serving weight in grams
- Pre-coalesced at import time (USDA) or at creation time (custom/recipe). **No runtime coalescing.**
- For USDA: best energy variant (Atwater General > Specific > plain Energy in kcal; kJ-only foods marked `is_complete=false`)
- For custom: copied from user-entered values at creation
- For recipe: computed from ingredient sanitized values at materialization

### 3.2 Data Model Changes

**foods table — new columns:**
```sql
ALTER TABLE foods ADD COLUMN tier SMALLINT;
  -- 0=USDA, 1=curated, 10=custom, 20=recipe, NULL=legacy/unclassified
ALTER TABLE foods ADD COLUMN imported_at TIMESTAMP;
ALTER TABLE foods ADD COLUMN is_complete BOOLEAN DEFAULT true;
ALTER TABLE foods ADD COLUMN sanitized_base_grams DECIMAL(10,2);
ALTER TABLE foods ADD COLUMN sanitized_calories DECIMAL(10,2);
ALTER TABLE foods ADD COLUMN sanitized_protein DECIMAL(10,2);
ALTER TABLE foods ADD COLUMN sanitized_carbs DECIMAL(10,2);
ALTER TABLE foods ADD COLUMN sanitized_fat DECIMAL(10,2);
ALTER TABLE foods ADD COLUMN sanitized_fiber DECIMAL(10,2);
```

**user_foods table — new columns (extend, don't rename):**
```sql
ALTER TABLE user_foods ADD COLUMN removed_at TIMESTAMP;
ALTER TABLE user_foods ADD COLUMN source_tier SMALLINT;
CREATE INDEX ix_user_foods_active ON user_foods (user_id) WHERE removed_at IS NULL;
CREATE INDEX ix_user_foods_food_id ON user_foods (food_id);
```

The SQLAlchemy model class will be renamed to `UserPantry` with `__tablename__ = "user_foods"`. Actual table rename deferred to a future low-risk migration.

**user_summary_nutrients — new column:**
```sql
ALTER TABLE user_summary_nutrients ADD COLUMN friendly_key VARCHAR(50);
  -- maps to friendly dict key: "calories", "protein", "carbs", "fat", "fiber"
```

**food_nutrients table — no changes.** Retained for:
- Source data for sanitization script (USDA)
- Vitamin/mineral storage and display
- Recipe materialization (full nutrient set)
- Historical audit trail

### 3.3 Dual-Write Strategy for Macros

After the refactor, macros exist in two places:
1. **`sanitized_*` columns on `foods`** — source of truth for the calculator, recipes, and summary display
2. **`food_nutrients` rows** — retained for vitamins/minerals, and as audit trail

**Who writes sanitized columns:**
| Food type | When written               | How                                            |
|-----------|----------------------------|------------------------------------------------|
| USDA      | Import/sanitization script | Best energy variant coalesced, carbs coalesced |
| Custom    | Food creation/edit         | Copied from user input                         |
| Recipe    | `_materialize_recipe()`    | Computed from ingredient `sanitized_*` values  |

Both `food_nutrients` rows AND `sanitized_*` columns are written during recipe materialization. The calculator reads only `sanitized_*`. Vitamin/mineral display reads `food_nutrients`.

### 3.4 Search Ranking

When searching for foods (logging or recipe building):
1. Query all tiers + pantry join
2. Rank: 🟢 Pantry (boost +100) > 🟡 Curated (boost +50) > 🔴 USDA (+0)
3. Apply Cohere Rerank with tier as boost signal (already integrated for search)
4. Return results with tier badge and inline macros (from `sanitized_*` fields)
5. Shared search modal: same component for food logging and recipe ingredient selection

### 3.5 Recipe Nutrition Simplification

After sanitization, recipe nutrition becomes:
```python
total = {k: Decimal("0") for k in ["calories", "protein", "carbs", "fat", "fiber"]}
for ingredient in recipe.ingredients:
    grams = get_quantity_in_grams(ingredient)
    scale = grams / Decimal(str(ingredient.food.sanitized_base_grams))
    for key in total:
        total[key] += getattr(ingredient.food, f"sanitized_{key}") * scale
per_serving = {k: v / recipe.servings for k, v in total.items()}
```

No coalescing. No by_id. No two-pass canonical system. ~10 lines.

### 3.6 Summary Display Simplification

`user_summary_nutrients` uses `friendly_key` for coalesced nutrients:
```python
if cfg.friendly_key:
    value = total_friendly[cfg.friendly_key]
elif cfg.formula:
    value = eval_formula(cfg.formula, total_friendly)  # always uses totals
elif cfg.nutrient_id:
    value = by_id_sum[cfg.nutrient_id]  # vitamins/minerals only
```

Custom formulas (WW points) always receive the **total** friendly dict, not per-ingredient.

### 3.7 Gram Conversion Unification

Currently duplicated:
- `RecipeService._get_quantity_in_grams()` — async, takes db session, handles parenthetical units
- `nutrient_calculator._get_gram_weight()` — sync, handles portion lookup

Post-refactor: single `get_quantity_in_grams(food, quantity, unit)` function in a shared module. Both recipe service and calculator import from it.

---

## 4. Execution Phases

### Phase 1: USDA Sanitization (Days 2-3)
**Goal:** Eliminate runtime coalescing by pre-computing macros at import time.

- [ ] Add columns to foods: `tier`, `imported_at`, `is_complete`, `sanitized_base_grams`, `sanitized_*`
- [ ] Mark SR Legacy foods deprecated, retain Foundation Foods
- [ ] Write sanitization script (pure SQL/Python, no LLM):
  - Energy: pick Atwater General > Specific > plain Energy (kcal only). kJ-only → `is_complete=false`.
  - Carbs: pick summation > difference
  - Protein/fat/fiber: direct copy from FoodNutrient
  - `sanitized_base_grams`: USDA=100, custom=`serving_size` gram-equivalent, recipe=`serving_size`
  - Completeness: `is_complete = false` if missing any of cal/protein/carb/fat
  - `imported_at = NOW()` for all existing foods
  - `tier = 0` for USDA, `10` for custom, `20` for recipe
- [ ] **Full population verification:** Run old runtime calc vs new sanitized values for ALL foods, flag any diff >1%
- [ ] Run sanitization on local DB → staging DB → prod DB

**Tests:**
- Sanitized values match expected for 20+ known foods (spot checks)
- `SELECT COUNT(*) FROM foods WHERE sanitized_calories IS NULL AND usda_fdc_id IS NOT NULL` = 0
- Full diff report: old vs new for all foods, <1% variance threshold
- `is_complete=false` correctly flags kJ-only and missing-macro foods

### Phase 2a: Pantry Migration (Day 4)
**Goal:** Extend user_foods to become the pantry.

- [ ] Add columns to `user_foods`: `removed_at`, `source_tier`
- [ ] Add indexes: `ix_user_foods_active` (partial, WHERE removed_at IS NULL), `ix_user_foods_food_id`
- [ ] Rename model class to `UserPantry` (keep `__tablename__ = "user_foods"`)
- [ ] Backfill `source_tier` from `foods.tier` for existing entries
- [ ] Auto-promote logic: on food_log create or recipe ingredient add, upsert pantry entry
- [ ] Pantry soft-delete: "remove from pantry" sets `removed_at`, re-add clears it and restores defaults

**Tests:**
- Auto-promotion on log creates pantry entry with correct defaults
- Auto-promotion on recipe ingredient add creates pantry entry
- Soft-delete preserves row, re-add restores
- Existing user_foods data intact after migration

### Phase 2b: Calculator Rewrite (Days 5-6)
**Goal:** Switch nutrition calculation to sanitized fields. Kill runtime coalescing.

- [ ] Unify gram conversion: single `get_quantity_in_grams(food, quantity, unit)` in shared module
- [ ] Rewrite `compute_item_nutrients` to use `sanitized_*` fields (no runtime coalescing)
- [ ] Rewrite `_compute_recipe_nutrients` using sanitized fields (~10 lines)
- [ ] Update `_materialize_recipe` to write `sanitized_*` columns on new Food
- [ ] Add `friendly_key` to `user_summary_nutrients`, migrate existing rows
- [ ] Rewrite `compute_summary_from_precomputed` to use `friendly_key`
- [ ] Custom formulas always use total friendly dict
- [ ] Remove `by_id` backfill and display_name hack (no longer needed)

**Verification:**
- Side-by-side comparison: old calc vs new calc for all existing food logs (should match within 1%)
- Recipe nutrition matches expected values for all existing recipes
- Summary endpoint returns correct calories for all energy variants
- WW points formula applied to totals, not per-ingredient

**Tests:**
- Unit tests for simplified `compute_item_nutrients`
- Unit tests for simplified `_compute_recipe_nutrients`
- Integration: create recipe, verify nutrition matches ingredient sum
- Integration: summary endpoint for USDA food with Atwater energy
- Regression: all 579+ existing tests pass

### Phase 2c: Search Ranking (Day 7)
**Goal:** Tier-weighted search results with pantry boost.

- [ ] Update search API: query all tiers, join pantry for boost
- [ ] Tier weight in ranking: pantry +100, curated +50, USDA +0
- [ ] Cohere Rerank integration with tier boost
- [ ] Return tier badge + inline macros in search results

**Tests:**
- Pantry foods rank above curated
- Curated foods rank above USDA
- Inline macros returned for all results

### Phase 3: Frontend Updates (Days 8-10)
**Goal:** Per-ingredient macro preview, tier badges, shared search modal.

- [ ] Shared food search component (food logging + recipe building)
- [ ] Tier badges in search results (🟢/🟡/🔴)
- [ ] Per-ingredient macro preview in recipe editor (cal/protein/carb/fat on confirm)
- [ ] Recipe total macros at bottom (excl. custom formulas)
- [ ] Add-to-pantry flow when selecting non-pantry food
- [ ] Pantry management page (view, edit defaults, remove, re-add)

### Phase 4: Portion Cleanup (Days 11-12)
**Goal:** Normalize USDA portions, remove garbage.

- [ ] Audit USDA portions: identify "undetermined", duplicates, garbage
- [ ] Sanitization rules: remove undetermined, normalize unit names, deduplicate
- [ ] Run on all DBs
- [ ] Prep state modeling: deferred to future phase (needs UX design)

### Phase 5: Curated Foods — AI-Generated Rules (Future)
**Goal:** Yellow tier (L1) with deterministic, AI-assisted curation.

- [ ] AI generates curation rules as code (SQL/Python), not LLM calls at runtime
- [ ] Rules reviewed by admin before execution
- [ ] Rules select canonical food per group (1 "Apple" from 25 variants)
- [ ] Rules assign reasonable default portions
- [ ] Rules are idempotent and versioned
- [ ] Rules cannot modify pantry items
- [ ] Re-curation preserves existing yellow foods

---

## 5. Migration Safety

### Backward Compatibility
- All new columns are additive (no existing columns removed)
- `user_foods` table stays as-is, new columns are nullable
- `friendly_key` is nullable (existing `nutrient_id` lookups work as fallback during transition)
- `food_nutrients` table untouched (vitamins/minerals, audit trail)

### Rollback Plan
- Phase 1: Drop sanitized columns, revert to runtime coalescing (no data loss)
- Phase 2a: Drop new columns from user_foods (pantry entries preserved)
- Phase 2b: Revert calculator to pre-refactor code (sanitized columns still there, just unused)
- Phase 3: Deploy old frontend bundle

### Data Verification
After each phase, run verification:
1. **Spot checks:** 20+ known foods with manually verified macros
2. **Full population diff:** Old runtime calc vs new sanitized values for ALL foods. Flag >1% variance.
3. **Null check:** No USDA food should have NULL sanitized_calories
4. **Historical log audit:** Compare daily totals for last 30 days of food logs, old vs new calc

### Known Retroactive Changes
After Phase 2b, historical food logs will show slightly different calorie counts where the old runtime coalescing picked a different energy variant than the sanitization script. This is intentional — the sanitized value is more correct. Differences should be <5% for any individual food.

---

## 6. Decisions Log

| # | Decision                                              | Rationale                                                                                                |
|---|-------------------------------------------------------|----------------------------------------------------------------------------------------------------------|
| 1 | Extend `user_foods` instead of creating `user_pantry` | Avoids table migration. Rename model class only.                                                         |
| 2 | No `macro_overrides` JSONB                            | Creates shadow data source, undermines sanitization. Users should create custom foods instead.           |
| 3 | `sanitized_base_grams` column                         | Normalizes scale factor. USDA=100, custom=serving grams, recipe=serving grams.                           |
| 4 | Explicit tier values (0/1/10/20)                      | Avoids NULL semantics confusion. Room for future tiers.                                                  |
| 5 | Keep `food_nutrients` table                           | Still needed for vitamins/minerals and audit trail. Dual-write for macros is documented and intentional. |
| 6 | AI generates curation rules, not curation itself      | Deterministic, idempotent, auditable. Rules are code.                                                    |
| 7 | Auto-promote to pantry on log or recipe add           | Reduces friction, pantry grows organically.                                                              |
| 8 | Phase 2 split into 2a/2b/2c                           | Each deployable independently. Calculator rewrite (2b) is riskiest, benefits from isolation.             |

---

## 7. Non-Goals

- Multi-user shared pantries
- Branded food database (Open Food Facts, barcode scanning) — future
- Micronutrient tracking in recipe view (vitamins, minerals)
- Meal planning / grocery lists
- Prep state modeling (future phase, needs UX design)
- `macro_overrides` on pantry entries (creates complexity, cut from v1)
