# Design: Food Tier System & Pantry

**Status:** Draft  
**Date:** 2026-03-31  
**Authors:** Aaron, Barney  

## Overview

Replace the current flat foods table with a tiered system that separates data quality levels and introduces a per-user "pantry" concept. Eliminate runtime energy/carb coalescing by sanitizing at import time.

## Problem Statement

1. USDA data has inconsistent energy variants (Atwater General, Atwater Specific, plain Energy) causing 0-calorie bugs in recipes and summary views
2. 8,000+ USDA foods with varying data quality overwhelm search and produce unreliable nutrition calculations
3. No distinction between "food I use regularly" and "food that exists in a database somewhere"
4. Recipe ingredient selection has no guardrails — user can pick an incomplete USDA food and get wrong results

## Architecture

### Food Tiers

Single `foods` table with a `tier` column:

| Tier | Color | Label | Description |
|------|-------|-------|-------------|
| 0 | 🔴 Red | USDA Raw | Sanitized USDA import. Complete macros. Searchable but unfamiliar. |
| 1 | 🟡 Yellow | Curated | Admin-curated common foods. Reasonable defaults. Trustworthy. |

"Green" is not a tier — it's **in the user's pantry** (any tier food + user's confirmed defaults).

### Pantry (per-user)

`user_pantry` join table:

```sql
CREATE TABLE user_pantry (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id),
    food_id INT NOT NULL REFERENCES foods(id),
    default_quantity DECIMAL(10,2),
    default_unit VARCHAR(50),
    macro_overrides JSONB,          -- nullable, overlay on food's base macros
    added_at TIMESTAMP DEFAULT NOW(),
    removed_at TIMESTAMP,           -- soft delete, preserves preferences
    UNIQUE(user_id, food_id)
);
```

Key behaviors:
- **Adding to pantry:** User confirms food, picks default qty/unit
- **Macro overrides:** Optional JSON overlay. `{"calories": 130}` overrides only calories, rest from base food.
- **Removing from pantry:** Sets `removed_at`, preserves row. Re-adding restores previous defaults.
- **Auto-promote:** Logging a food or adding to recipe auto-adds to pantry with the qty/unit used.

### USDA Sanitization (Import-Time)

Run during USDA import as a DB operation (no LLM):

1. **Energy coalescing:** Pick best variant (Atwater General > Specific > plain), store as single `calories` field
2. **Carb coalescing:** Pick summation > difference, store as single `carbs` field  
3. **Completeness check:** Flag foods missing cal/protein/carb/fat as `is_complete=false`
4. **Portion normalization:** Strip "undetermined", normalize unit names
5. **Import date:** `imported_at` timestamp on each food. Search returns latest import per food name.
6. **Historical preservation:** Old imports stay in DB (referenced by existing pantry entries and recipes). Search only shows latest.

Post-sanitization, **no runtime energy/carb coalescing needed anywhere.**

### AI-Generated Curation Rules (Future Phase)

Yellow tier (L1) curation process:
1. AI analyzes USDA food groups and generates deterministic curation rules
2. Rules are code (SQL/Python), not LLM calls
3. Rules are reviewed by admin before execution
4. Rules select canonical food per group (e.g., one "Apple" from 25 variants)
5. Rules assign reasonable default portions
6. Re-running rules produces identical results (idempotent)
7. Rules cannot modify foods already in any user's pantry

### Prep States (Phase 2 — Tabled)

Volume portions vary by preparation (1 cup chopped ≠ 1 cup whole). 

Deferred to Phase 2. Will likely be a portion modifier (`state` column on portions table): `cup/whole=120g`, `cup/chopped=150g`. By-weight portions unaffected.

## Data Model Changes

### Foods Table (modified)

```sql
ALTER TABLE foods ADD COLUMN tier SMALLINT NOT NULL DEFAULT 0;  -- 0=USDA, 1=curated
ALTER TABLE foods ADD COLUMN imported_at TIMESTAMP;
ALTER TABLE foods ADD COLUMN is_complete BOOLEAN DEFAULT true;
ALTER TABLE foods ADD COLUMN sanitized_calories DECIMAL(10,2);   -- pre-coalesced
ALTER TABLE foods ADD COLUMN sanitized_carbs DECIMAL(10,2);      -- pre-coalesced
ALTER TABLE foods ADD COLUMN sanitized_protein DECIMAL(10,2);
ALTER TABLE foods ADD COLUMN sanitized_fat DECIMAL(10,2);
ALTER TABLE foods ADD COLUMN sanitized_fiber DECIMAL(10,2);
```

### user_pantry Table (new)

Replaces `user_foods` for the "registered foods" concept.

### Migration

1. Existing `user_foods` → `user_pantry` (same concept, new name)
2. Existing custom foods → tier stays NULL (user-created, not USDA)
3. All USDA foods → tier=0, run sanitization, set `imported_at=today`
4. Existing recipes → ingredient food_ids unchanged, just need tier backfill
5. Non-destructive. No data loss.

## UX Flows

### Searching for Food (Log or Recipe)

1. Search input → query all tiers
2. Results ranked: 🟢 Pantry > 🟡 Curated > 🔴 USDA (use Cohere Rerank with tier weighting)
3. Each result shows: name, tier badge, per-serving macros
4. Picking a pantry food → immediate (defaults pre-set)
5. Picking a yellow/red food → add-to-pantry modal: confirm macros, set defaults → logged/added

### Building a Recipe (Manual)

1. Same search modal as food logging (shared component)
2. Pick ingredient → if not in pantry, auto-add via confirmation
3. Each confirmed ingredient shows inline macros immediately (cal/protein/carb/fat)
4. Summary at bottom: total and per-serving macros (excl. custom formulas)

### Building a Recipe (Photo)

1. Snap photo → AI extracts ingredients + quantities
2. AI matches each ingredient: pantry first, then yellow, then red (rerank)
3. Confirmation screen shows each ingredient with match + macros
4. User confirms/edits each row
5. Confirmed matches auto-add to pantry
6. Recipe saves with all-pantry ingredients

### Recipe Nutrition Display

- Per-ingredient: show cal/protein/carb/fat inline on each row
- Per-serving total: show at bottom
- Custom formulas (WW points): calculated on per-serving totals only, not per-ingredient

## Phases

### Phase 1: Foundation
- [ ] Add `tier`, `imported_at`, `is_complete` columns to foods
- [ ] USDA sanitization script (energy/carb coalescing, completeness, portion cleanup)
- [ ] Create `user_pantry` table, migrate from `user_foods`
- [ ] Simplify `compute_item_nutrients` — no runtime coalescing (use sanitized fields)
- [ ] Simplify `_compute_recipe_nutrients` — just sum friendly values
- [ ] Update search ranking: pantry > curated > USDA
- [ ] Per-ingredient macro preview in recipe editor
- [ ] Auto-promote to pantry on log/recipe-add
- [ ] Summary config: use `friendly_key` instead of `nutrient_id` for coalesced nutrients
- [ ] Custom formulas use total friendly values (not per-ingredient)

### Phase 2: Polish
- [ ] Prep state modeling for volume portions
- [ ] AI-generated curation rules for yellow tier
- [ ] Pantry management UI (remove, edit defaults, edit macro overrides)
- [ ] Barcode scanning → auto-register from Open Food Facts
- [ ] Improved photo flow with batch confirmation

## Non-Goals (For Now)
- Multi-user shared pantries
- Branded food database (beyond what's in USDA)
- Meal planning / grocery lists
- Micronutrient tracking (vitamins, minerals) in recipe view
