# Phase 1: USDA Sanitization — Implementation Plan

## Goal

Add 11 new columns to the `foods` table and pre-compute 5 core macros (calories, protein, carbs, fat, fiber) from `food_nutrients`, eliminating the need for runtime energy/carb coalescing. Also re-import the full Foundation Foods dataset.

## Tech Stack

- Python 3.11, FastAPI, SQLAlchemy async, asyncpg, PostgreSQL 16
- Alembic for migrations
- pytest for testing (579 existing tests, all passing)
- Linter: `uv run ruff check .`
- Test command: `uv run pytest tests/ -q --tb=short`
- Project root: `/home/aaron/source/whati8`

## Steps

### Step 1: Alembic Migration — Add Columns + Update Model

**What:** Create Alembic migration to add 11 new columns to `foods` table. Update the `Food` SQLAlchemy model to include the new columns. Add indexes on `tier` and `data_source`.

**Acceptance Criteria:**
- Alembic migration runs successfully (upgrade + downgrade)
- `Food` model has all 11 new mapped columns with correct types
- All new columns are nullable or have server defaults (backward-compatible)
- Indexes `ix_foods_tier` and `ix_foods_data_source` are created
- All 579 existing tests still pass
- Migration is reversible (downgrade drops the columns and indexes)

**Columns:**
| Column | SQLAlchemy Type | Server Default | Nullable |
|--------|----------------|----------------|----------|
| tier | SmallInteger | — | True |
| data_source | String(50) | — | True |
| is_deprecated | Boolean | "false" | False |
| imported_at | DateTime | — | True |
| is_complete | Boolean | "true" | False |
| sanitized_base_grams | Numeric(10,2) | — | True |
| sanitized_calories | Numeric(10,2) | — | True |
| sanitized_protein | Numeric(10,2) | — | True |
| sanitized_carbs | Numeric(10,2) | — | True |
| sanitized_fat | Numeric(10,2) | — | True |
| sanitized_fiber | Numeric(10,2) | — | True |

### Step 2: Sanitization Script — USDA Foods

**What:** Create `scripts/sanitize_foods.py` that populates `tier`, `data_source`, `sanitized_base_grams`, and 5 sanitized macro columns for all USDA foods. Includes energy/carb coalescing logic.

**Acceptance Criteria:**
- Script connects to DB directly (sync psycopg2, not async SQLAlchemy — simpler for a one-shot script)
- Accepts `--database-url` flag or reads `DATABASE_URL` from env
- Idempotent: safe to re-run (uses UPDATE, not INSERT)
- Sets `tier=0` for all USDA foods
- Sets `data_source` = `foundation` (FDC >= 300K or has Atwater energy) or `sr_legacy`
- Sets `sanitized_base_grams=100` for all USDA foods
- Energy coalescing: Atwater General > Specific > plain Energy
- Carb coalescing: summation > difference
- Direct copy: protein, fat, fiber
- Sets `is_complete=false` when cal/protein/carb/fat is NULL
- Sets `imported_at` and `is_deprecated=false`
- Prints summary stats (sanitized count by data_source, incomplete count)
- Completes in <60s for ~8K foods

### Step 3: Sanitization Script — Custom + Recipe Foods

**What:** Extend `scripts/sanitize_foods.py` to handle custom foods (tier=10) and recipe foods (tier=20).

**Acceptance Criteria:**
- Custom foods: `tier=10`, `data_source='custom'`
- Custom foods: `sanitized_base_grams` computed from serving unit:
  - Gram units → `serving_size` directly
  - Mass units (oz/lb/kg) → converted to grams
  - Volume units → portion gram_weight lookup, fallback to water density
  - Custom units → portion gram_weight lookup, fallback to `serving_size` grams
- Custom foods: 5 macros copied from `food_nutrients` (no coalescing)
- Recipe foods: `tier=20`, `data_source='recipe'`
- Recipe foods: `sanitized_base_grams = serving_size`
- Recipe foods: macros computed by summing ingredient sanitized values, divided by servings
- Recipe sanitization runs AFTER USDA + custom (dependency order)
- Only current (non-expired) recipe foods are sanitized
- Sets `is_complete` appropriately for both types
- Prints summary stats for custom + recipe foods

### Step 4: Verification Script + Foundation Re-Import

**What:** Create `scripts/verify_sanitization.py` that validates all sanitized values against source data. Also update the Foundation Foods import to fill the gap (~265 → ~1000).

**Acceptance Criteria:**
- Verification script compares sanitized values against `food_nutrients` source:
  - USDA: sanitized_calories should match best energy variant in food_nutrients (within 0.01)
  - Custom: sanitized values should match food_nutrients exactly (within 0.01)
  - Recipe: sanitized values should match ingredient-sum computation (within 0.1 for rounding)
- Reports: total foods checked, pass/fail counts by type, list of any failures
- Verifies: zero NULL `sanitized_calories` for USDA foods
- Reports: `is_complete=false` count
- Foundation re-import: downloads latest dataset, imports new foods, deduplicates
- Import logs: foods created, updated, duplicates removed
- After re-import + re-sanitize: verification passes for all foods

## Changelog

Track in `CHANGELOG.md` at project root.
