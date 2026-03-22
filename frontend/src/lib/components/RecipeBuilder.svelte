<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import RecipeIngredientRow from './RecipeIngredientRow.svelte';
  import PhotoCapture from './PhotoCapture.svelte';
  import { createRecipe } from '../api/recipe';
  import type { Recipe, CreateRecipePayload } from '../api/recipe';
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
      food_id?: number;
      food_name?: string;
      quantity?: number;
      unit?: string;
      portion_description?: string;
      searchText?: string;
    };
  }

  let recipeName = '';
  let servings = 1;
  let servingUnit = 'serving';
  let ingredients: IngredientRow[] = [];
  let saving = false;
  let showPhotoCapture = false;

  // Initialize with prefill lines
  if (prefillLines.length > 0) {
    ingredients = prefillLines.map((line, i) => ({
      id: `prefill-${i}`,
      state: 'editing' as const,
      data: { searchText: line },
    }));
  }

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
    const { food_id, food_name, quantity, unit, portion_description } = event.detail;
    ingredients[index] = {
      ...ingredients[index],
      state: 'locked',
      data: { food_id, food_name, quantity, unit, portion_description },
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
    <h2 class="text-lg font-bold text-gray-900">Create Recipe</h2>
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
      <p class="text-xs text-gray-500">Save to calculate nutrition</p>
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
