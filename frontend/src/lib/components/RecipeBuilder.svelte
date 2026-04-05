<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import RecipeIngredientRow from './RecipeIngredientRow.svelte';
  import PhotoCapture from './PhotoCapture.svelte';
  import { 
    createRecipe, 
    getRecipe, 
    updateRecipe, 
    addIngredient as addIngredientToRecipe, 
    removeIngredient as removeIngredientFromRecipe 
  } from '../api/recipe';
  import type { Recipe, CreateRecipePayload, RecipeIngredient } from '../api/recipe';
  import { recognizePhoto } from '../api/photo';
  import type { RecognitionResult } from '../api/photo';
  import { toastStore } from '../stores/toast';

  export let recipeId: number | null = null;
  export let prefillLines: string[] = [];

  const dispatch = createEventDispatcher<{
    saved: Recipe;
    close: void;
  }>();

  interface IngredientRow {
    id: string;
    state: 'editing' | 'locked';
    data: {
      ingredient_id?: number; // For tracking existing ingredients
      food_id?: number;
      food_name?: string;
      quantity?: number;
      unit?: string;
      portion_description?: string;
      searchText?: string;
      summaryNutrients?: Array<{ name: string; value: number; unit: string }> | null;
    };
  }

  let recipeName = '';
  let servings = 1;
  let servingUnit = 'serving';
  let ingredients: IngredientRow[] = [];
  let saving = false;
  let showPhotoCapture = false;
  let loadedRecipe: Recipe | null = null;
  let loadedIngredients: RecipeIngredient[] = [];
  let perServingNutrition: string | null = null;

  // Initialize with prefill lines
  if (prefillLines.length > 0) {
    ingredients = prefillLines.map((line, i) => ({
      id: `prefill-${i}`,
      state: 'editing' as const,
      data: { searchText: line },
    }));
  }

  // Load recipe if editing
  onMount(async () => {
    if (recipeId !== null) {
      try {
        loadedRecipe = await getRecipe(recipeId);
        recipeName = loadedRecipe.name;
        servings = loadedRecipe.servings;
        servingUnit = loadedRecipe.serving_unit;
        
        // Store loaded ingredients for comparison
        loadedIngredients = [...loadedRecipe.ingredients];
        
        // Populate ingredients as locked rows
        ingredients = loadedRecipe.ingredients.map((ing) => ({
          id: `loaded-${ing.id}`,
          state: 'locked' as const,
          data: {
            ingredient_id: ing.id,
            food_id: ing.food_id,
            food_name: ing.food_name,
            quantity: ing.quantity,
            unit: ing.unit,
            portion_description: ing.portion_description,
          },
        }));

        // Format per-serving nutrition
        const ps = loadedRecipe.per_serving;
        const parts = [`🔥 ${Math.round(ps.calories)} cal`];
        if (ps.protein_g > 0) parts.push(`🥩 ${Math.round(ps.protein_g)}g protein`);
        if (ps.carbs_g > 0) parts.push(`🍞 ${Math.round(ps.carbs_g)}g carbs`);
        if (ps.fat_g > 0) parts.push(`🧈 ${Math.round(ps.fat_g)}g fat`);
        if (ps.fiber_g > 0) parts.push(`🌾 ${Math.round(ps.fiber_g)}g fiber`);
        perServingNutrition = parts.join(' · ');
      } catch (err: any) {
        toastStore.error(err?.message || 'Failed to load recipe');
        dispatch('close');
      }
    }
  });

  function addIngredient() {
    ingredients = [
      ...ingredients,
      {
        id: `ing-${Date.now()}-${Math.random()}`,
        state: 'editing',
        data: {},
      },
    ];
  }

  function handleIngredientLock(index: number, event: CustomEvent) {
    const { food_id, food_name, quantity, unit, portion_description, summaryNutrients } = event.detail;
    ingredients[index] = {
      ...ingredients[index],
      state: 'locked',
      data: { food_id, food_name, quantity, unit, portion_description, summaryNutrients },
    };
    ingredients = [...ingredients];
  }

  function handleIngredientUnlock(index: number) {
    ingredients[index] = {
      ...ingredients[index],
      state: 'editing',
    };
    ingredients = [...ingredients];
  }

  function handleIngredientRemove(index: number) {
    ingredients = ingredients.filter((_, i) => i !== index);
  }

  async function handleSave() {
    if (!recipeName.trim()) {
      toastStore.error('Please enter a recipe name');
      return;
    }

    const lockedIngredients = ingredients.filter(i => i.state === 'locked');
    if (lockedIngredients.length === 0) {
      toastStore.error('Please add at least one ingredient');
      return;
    }

    const editingCount = ingredients.filter(i => i.state === 'editing').length;
    if (editingCount > 0) {
      toastStore.error(`${editingCount} ingredient(s) not matched. Lock all ingredients first.`);
      return;
    }

    saving = true;
    try {
      if (recipeId === null) {
        // Create mode
        const payload: CreateRecipePayload = {
          name: recipeName.trim(),
          servings,
          serving_unit: servingUnit.trim() || 'serving',
          ingredients: lockedIngredients.map(i => ({
            food_id: i.data.food_id!,
            quantity: i.data.quantity!,
            unit: i.data.unit!,
            portion_description: i.data.portion_description!,
          })),
        };

        const recipe = await createRecipe(payload);
        toastStore.success(`Recipe "${recipe.name}" created!`);
        dispatch('saved', recipe);
      } else {
        // Edit mode - compare and update
        const currentIngredientIds = new Set(
          lockedIngredients
            .filter(i => i.data.ingredient_id !== undefined)
            .map(i => i.data.ingredient_id!)
        );
        const loadedIngredientIds = new Set(loadedIngredients.map(i => i.id));

        // Removed ingredients
        for (const loaded of loadedIngredients) {
          if (!currentIngredientIds.has(loaded.id)) {
            await removeIngredientFromRecipe(recipeId, loaded.id);
          }
        }

        // New ingredients
        for (const ing of lockedIngredients) {
          if (ing.data.ingredient_id === undefined) {
            await addIngredientToRecipe(recipeId, {
              food_id: ing.data.food_id!,
              quantity: ing.data.quantity!,
              unit: ing.data.unit!,
              portion_description: ing.data.portion_description!,
            });
          }
        }

        // Update recipe metadata if changed
        if (
          recipeName.trim() !== loadedRecipe?.name ||
          servings !== loadedRecipe?.servings ||
          servingUnit.trim() !== loadedRecipe?.serving_unit
        ) {
          await updateRecipe(recipeId, {
            name: recipeName.trim(),
            servings,
            serving_unit: servingUnit.trim() || 'serving',
          });
        }

        // Reload recipe to get updated nutrition
        const updatedRecipe = await getRecipe(recipeId);
        toastStore.success(`Recipe "${updatedRecipe.name}" updated!`);
        dispatch('saved', updatedRecipe);
      }
    } catch (err: any) {
      toastStore.error(err?.message || 'Failed to save recipe');
    } finally {
      saving = false;
    }
  }

  function handleClose() {
    dispatch('close');
  }

  async function handlePhotoResult(e: CustomEvent<RecognitionResult>) {
    showPhotoCapture = false;
    const result = e.detail;
    
    // Each item becomes a new editing-mode row
    const newRows: IngredientRow[] = result.items.map((item, i) => ({
      id: `photo-${Date.now()}-${i}`,
      state: 'editing' as const,
      data: { searchText: item.name },
    }));

    ingredients = [...ingredients, ...newRows];
    toastStore.info(`Added ${newRows.length} ingredient(s) from photo`);
  }

  $: lockedCount = ingredients.filter(i => i.state === 'locked').length;
  $: editingCount = ingredients.filter(i => i.state === 'editing').length;
  $: canSave = recipeName.trim().length > 0 && lockedCount > 0 && editingCount === 0;
</script>

<div class="flex flex-col h-full bg-gray-50">
  <!-- Header -->
  <div class="flex-shrink-0 bg-white border-b border-gray-200 px-4 py-4">
    <h2 class="text-lg font-bold text-gray-900">{recipeId === null ? 'Create Recipe' : 'Edit Recipe'}</h2>
    <p class="text-sm text-gray-500 mt-0.5">Build your recipe from ingredients</p>
  </div>

  <!-- Content -->
  <div class="flex-1 overflow-y-auto p-4 space-y-4">
    <!-- Recipe metadata -->
    <div class="bg-white rounded-xl p-4 space-y-3">
      <div>
        <label class="block text-xs font-semibold text-gray-700 mb-1">Recipe Name</label>
        <input
          type="text"
          bind:value={recipeName}
          placeholder="e.g. Chicken Salad"
          class="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-600"
        />
      </div>
      <div class="flex gap-3">
        <div class="flex-1">
          <label class="block text-xs font-semibold text-gray-700 mb-1">Servings</label>
          <input
            type="number"
            bind:value={servings}
            min="1"
            step="1"
            class="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-600"
          />
        </div>
        <div class="flex-1">
          <label class="block text-xs font-semibold text-gray-700 mb-1">Unit Name</label>
          <input
            type="text"
            bind:value={servingUnit}
            placeholder="serving"
            class="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-600"
          />
        </div>
      </div>
    </div>

    <!-- Ingredients -->
    <div class="space-y-3">
      <div class="flex items-center justify-between">
        <h3 class="text-sm font-bold text-gray-900">Ingredients</h3>
        {#if editingCount > 0}
          <span class="text-xs text-orange-600 font-semibold">{editingCount} not matched</span>
        {/if}
      </div>

      {#each ingredients as ing, i (ing.id)}
        <RecipeIngredientRow
          ingredient={ing.data}
          state={ing.state}
          recipeId={recipeId}
          on:lock={(e) => handleIngredientLock(i, e)}
          on:unlock={() => handleIngredientUnlock(i)}
          on:remove={() => handleIngredientRemove(i)}
        />
      {/each}

      <button
        type="button"
        on:click={addIngredient}
        class="w-full py-3 px-4 bg-white border border-gray-300 border-dashed rounded-xl text-sm font-semibold text-gray-600 hover:bg-gray-50 hover:border-gray-400"
      >
        + Add Ingredient
      </button>
    </div>

    <!-- Nutrition preview -->
    <div class="bg-white rounded-xl p-4">
      <h3 class="text-sm font-bold text-gray-900 mb-2">Per Serving</h3>
      {#if perServingNutrition}
        <p class="text-xs text-gray-700">{perServingNutrition}</p>
      {:else}
        <p class="text-xs text-gray-500">Save to calculate nutrition</p>
      {/if}
    </div>
  </div>

  <!-- Actions -->
  <div class="flex-shrink-0 bg-white border-t border-gray-200 p-4 space-y-2">
    <button
      type="button"
      on:click={() => showPhotoCapture = true}
      class="w-full py-3 px-4 bg-gray-100 text-gray-700 rounded-xl text-sm font-semibold hover:bg-gray-200 flex items-center justify-center gap-2"
    >
      📷 Scan Recipe
    </button>
    <div class="flex gap-2">
      <button
        type="button"
        on:click={handleClose}
        class="flex-1 py-3 px-4 bg-gray-100 text-gray-700 rounded-xl text-sm font-semibold hover:bg-gray-200"
      >
        Cancel
      </button>
      <button
        type="button"
        on:click={handleSave}
        disabled={!canSave || saving}
        class="flex-1 py-3 px-4 bg-primary-600 text-white rounded-xl text-sm font-semibold hover:bg-primary-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
      >
        {saving ? 'Saving...' : 'Save Recipe'}
      </button>
    </div>
  </div>
</div>

{#if showPhotoCapture}
  <div class="fixed inset-0 bg-black bg-opacity-90 z-50 flex items-center justify-center">
    <div class="w-full max-w-lg">
      <PhotoCapture
        on:result={handlePhotoResult}
      />
      <button
        type="button"
        on:click={() => showPhotoCapture = false}
        class="mt-4 w-full py-3 bg-white text-gray-900 rounded-xl font-semibold"
      >
        Close
      </button>
    </div>
  </div>
{/if}
