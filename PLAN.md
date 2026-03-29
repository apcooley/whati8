# PLAN.md — Fix Manual Add Food Process

## Goal
Rename `PhotoResults` → `FoodEntryForm` and reuse it for both photo-based (prepopulated) and manual (empty) food entry. Delete the broken `ManualFoodForm`.

## Problem
1. **ManualFoodForm is broken and minimal** — only has name/brand/serving/macros, broken two-step flow
2. **PhotoResults already has everything** — custom units, volume, weight, qty, 30+ micronutrients
3. **Two components doing the same job** — DRY violation

## Solution
One component, two modes: prepopulated (from photo) or empty (manual entry).

## Steps

### Step 1: Rename PhotoResults → FoodEntryForm
- Rename `PhotoResults.svelte` → `FoodEntryForm.svelte`
- Make the `items` prop optional with sensible empty defaults (one blank item)
- When `items` is empty/not provided, render one blank food entry form
- Same `save` and `close` events

### Step 2: Wire manual mode into AddFoodView
- Replace `ManualFoodForm` import with `FoodEntryForm`
- Manual tab: render `<FoodEntryForm />` with no items (empty form)
- Photo tab: render `<FoodEntryForm items={photoResult.items} />` (prepopulated)
- Both use the same `handlePhotoSave` handler (rename to `handleFoodSave`)
- Delete `handleManualCreated` and the RegisterSheet detour

### Step 3: Extract shared constants
- Move `CORE_NUTRIENTS`, `NUTRIENT_LABELS`, `ALL_OPTIONAL`, `VOLUME_TO_ML` to `lib/constants/nutrients.ts`
- Import in `FoodEntryForm.svelte`

### Step 4: Cleanup
- Delete `ManualFoodForm.svelte`
- Build frontend to verify
- Verify photo flow still works
