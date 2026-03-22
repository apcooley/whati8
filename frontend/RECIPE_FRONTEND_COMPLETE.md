# Recipe Frontend - Step 4 Complete ✅

## Summary

Successfully implemented the recipe creation/editing UI for the whati8 food tracking app. The frontend is now ready to create recipes by combining foods with portions and quantities.

## Files Created

### 1. `/src/lib/api/recipe.ts` (2.4 KB)
Complete API client for recipe operations:
- `createRecipe()` - Create new recipe with ingredients
- `listRecipes()` - Get all recipes
- `getRecipe(id)` - Get single recipe details
- `updateRecipe(id, data)` - Update recipe metadata
- `addIngredient()` - Add ingredient to recipe
- `removeIngredient()` - Remove ingredient from recipe
- `canAddFood()` - Check circular dependency
- `deleteRecipe(id)` - Delete recipe

TypeScript interfaces:
- `Recipe` - Full recipe with ingredients and nutrition
- `RecipeIngredient` - Single ingredient with food details
- `PerServingNutrition` - Nutritional breakdown per serving
- `CreateRecipePayload` - Data for creating new recipe

### 2. `/src/lib/components/RecipeIngredientRow.svelte` (7.9 KB)
Interactive ingredient row component with two states:

**Editing State:**
- Search-as-you-type input (debounced 300ms)
- Prioritizes recent foods from `/profile/foods/recent`
- Falls back to USDA search via `/foods/search`
- Dropdown showing food names with calorie info
- Quantity input + portion selector
- Checkmark button to lock ingredient

**Locked State:**
- Read-only display: food name, quantity, unit
- Pencil icon to unlock and edit
- Trash icon to remove

Props:
- `ingredient` - Current ingredient data
- `state` - 'editing' | 'locked'
- `recipeId` - For dependency checks (not implemented in MVP)

Events:
- `lock` - Ingredient fully matched
- `unlock` - User wants to edit
- `remove` - Delete ingredient
- `addFood` - Navigate to add food flow (not implemented)

### 3. `/src/lib/components/RecipeBuilder.svelte` (8.4 KB)
Main recipe creation interface:

**Features:**
- Recipe name input
- Servings count + unit name fields
- Dynamic ingredient list
- "Add Ingredient" button
- Photo scan for bulk ingredient import
- Live validation (shows count of unmatched ingredients)
- Save/Cancel actions

**Validation:**
- Recipe name required
- At least one ingredient required
- All ingredients must be locked (matched with food + quantity)
- Shows error toasts for validation failures

**Photo Integration:**
- "📷 Scan Recipe" button
- Opens camera via PhotoCapture component
- Posts to `/photo/recognize` endpoint
- Each recognized item becomes a new editing-mode row
- Pre-fills search text with AI-extracted ingredient name

**Save Flow (MVP - Create Only):**
1. Validate: name, ingredients, all locked
2. Build `CreateRecipePayload` from locked ingredients
3. POST to `/recipes/` endpoint
4. Show success toast
5. Dispatch `saved` event with recipe data

Props:
- `recipeId` - null for create, number for edit (edit not implemented in MVP)
- `prefillLines` - Array of strings to pre-populate ingredients

Events:
- `saved` - Recipe created successfully
- `close` - User cancelled

### 4. Modified `/src/lib/components/AddFoodView.svelte`
Added recipe mode to the Add Food flow:

**Changes:**
- Added `'recipe'` to mode type: `'search' | 'manual' | 'recipe'`
- Added "🍳 Recipe" tab in switcher
- Added "🍳 Create Recipe" button in search mode (between photo and barcode)
- Integrated `<RecipeBuilder>` component for recipe mode
- Added `handleRecipeSaved()` handler:
  - Shows success toast
  - Invalidates profileFoods store
  - Switches back to search mode
  - Navigates to log view

## Build Status

✅ **Build successful** - No errors, only accessibility warnings (existing)

```bash
cd /home/aaron/source/whati8/frontend
npx vite build
```

Output:
- `dist/assets/index-CUXMEila.js` - 238.89 kB (67.46 kB gzipped)
- `dist/assets/index-DJCVoxmu.css` - 25.36 kB (5.29 kB gzipped)

## Key Patterns Followed

✅ All buttons have `type="button"` (mobile Edge compatibility)
✅ Import `apiRequest` from `'../api/client'`
✅ Import `toastStore` from `'../stores/toast'`
✅ Tailwind classes: rounded-xl, primary-600, gray-50, etc.
✅ Debounced search inputs (300ms)
✅ Svelte 4 syntax: `export let`, `$:`, `createEventDispatcher`, `on:click`

## API Endpoints Used

- `GET /profile/foods/recent` - Recent foods for search priority
- `GET /foods/search?q=term` - USDA food search
- `GET /foods/{food_id}/portions` - Available portions for a food
- `POST /recipes/` - Create new recipe
- `POST /photo/recognize` - Photo recognition for ingredient scan

## Not Implemented (Future)

These were marked as "for later" in the spec:

1. **Recipe editing** - `recipeId` prop exists but edit flow not implemented
2. **Circular dependency checks** - `canAddFood()` API exists but not called
3. **Live nutrition calculation** - Shows "Save to calculate nutrition" placeholder
4. **Add Food from recipe** - `addFood` event exists but not wired up

## Testing Checklist

Manual testing recommended:

- [ ] Open Add Food view
- [ ] Click "🍳 Recipe" tab
- [ ] Enter recipe name (e.g., "Chicken Salad")
- [ ] Set servings (e.g., 4)
- [ ] Add ingredient, search for food (e.g., "chicken breast")
- [ ] Select food from dropdown
- [ ] Enter quantity and select portion
- [ ] Lock ingredient with checkmark
- [ ] Add second ingredient (repeat process)
- [ ] Try to save with unmatched ingredient (should show error)
- [ ] Lock all ingredients and save
- [ ] Verify success toast and navigation to log
- [ ] Test photo scan button (opens camera)
- [ ] Test cancel button (returns to search mode)

## Notes

- The recipe frontend is **MVP-complete** for creation flow
- Backend API is assumed to be fully implemented
- Frontend matches backend schema from Step 3
- Photo recognition uses existing PhotoCapture component
- Recipe created foods are automatically registered to user's food list
- App runs at http://localhost:9428

## Next Steps

If recipe editing is needed:
1. Check `recipeId` prop in RecipeBuilder
2. If not null, fetch recipe via `getRecipe(recipeId)`
3. Populate form fields and ingredients
4. On save, use `updateRecipe()` + `addIngredient()` / `removeIngredient()` calls
5. Track ingredient changes (added/removed/modified)

For circular dependency prevention:
1. Before locking an ingredient in RecipeIngredientRow
2. Call `canAddFood(recipeId, foodId)` if recipeId exists
3. Show error if `allowed: false`
4. Prevent locking the ingredient
