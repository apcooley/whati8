<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import { listRecipes, deleteRecipe } from '../api/recipe';
  import type { Recipe } from '../api/recipe';
  import { toastStore } from '../stores/toast';

  const dispatch = createEventDispatcher<{
    edit: number;
    create: void;
    deleted: void;
  }>();

  let recipes: Recipe[] = [];
  let loading = true;
  let error: string | null = null;

  async function loadRecipes() {
    loading = true;
    error = null;
    try {
      recipes = await listRecipes();
    } catch (err: any) {
      error = err?.message || 'Failed to load recipes';
    } finally {
      loading = false;
    }
  }

  async function handleDelete(recipe: Recipe) {
    if (!confirm(`Delete "${recipe.name}"?`)) return;
    
    try {
      await deleteRecipe(recipe.id);
      toastStore.success(`Deleted "${recipe.name}"`);
      recipes = recipes.filter(r => r.id !== recipe.id);
      dispatch('deleted');
    } catch (err: any) {
      toastStore.error(err?.message || 'Failed to delete recipe');
    }
  }

  function handleEdit(recipeId: number) {
    dispatch('edit', recipeId);
  }

  function handleCreate() {
    dispatch('create');
  }

  function formatNutrition(recipe: Recipe): string {
    const ps = recipe.per_serving;
    const parts = [
      `🔥 ${Math.round(ps.calories)}`,
    ];
    if (ps.protein_g > 0) parts.push(`🥩 ${Math.round(ps.protein_g)}g`);
    if (ps.carbs_g > 0) parts.push(`🍞 ${Math.round(ps.carbs_g)}g`);
    if (ps.fat_g > 0) parts.push(`🧈 ${Math.round(ps.fat_g)}g`);
    return parts.join(' · ');
  }

  onMount(loadRecipes);

  // Export refresh method for parent
  export function refresh() {
    loadRecipes();
  }
</script>

<div class="flex flex-col h-full bg-gray-50">
  <!-- Header -->
  <div class="flex-shrink-0 bg-white border-b border-gray-200 px-4 py-4">
    <h2 class="text-lg font-bold text-gray-900">🍳 My Recipes</h2>
    <p class="text-sm text-gray-500 mt-0.5">Your saved recipe collection</p>
  </div>

  <!-- Content -->
  <div class="flex-1 overflow-y-auto p-4 space-y-3">
    {#if loading}
      <div class="flex items-center justify-center py-12">
        <div class="text-gray-500 text-sm">Loading recipes...</div>
      </div>
    {:else if error}
      <div class="bg-red-50 border border-red-200 rounded-xl p-4">
        <p class="text-sm text-red-800">{error}</p>
        <button
          type="button"
          on:click={loadRecipes}
          class="mt-2 text-sm text-red-600 font-semibold hover:text-red-700"
        >
          Try Again
        </button>
      </div>
    {:else if recipes.length === 0}
      <div class="flex flex-col items-center justify-center py-12 px-4">
        <div class="text-4xl mb-3">🍳</div>
        <p class="text-gray-600 text-sm text-center mb-4">
          No recipes yet. Create your first one!
        </p>
        <button
          type="button"
          on:click={handleCreate}
          class="px-6 py-3 bg-primary-600 text-white rounded-xl text-sm font-semibold hover:bg-primary-700"
        >
          + New Recipe
        </button>
      </div>
    {:else}
      {#each recipes as recipe (recipe.id)}
        <div class="bg-white border border-gray-200 rounded-xl p-4">
          <div class="flex items-start justify-between gap-3 mb-2">
            <div class="flex-1 min-w-0">
              <h3 class="text-base font-bold text-gray-900 truncate">{recipe.name}</h3>
              <p class="text-xs text-gray-600 mt-0.5">
                {recipe.servings} {recipe.servings === 1 ? recipe.serving_unit : `${recipe.serving_unit}s`}
                · {recipe.ingredients.length} ingredient{recipe.ingredients.length === 1 ? '' : 's'}
              </p>
            </div>
            <div class="flex gap-2 flex-shrink-0">
              <button
                type="button"
                on:click={() => handleEdit(recipe.id)}
                class="p-2 text-gray-600 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                title="Edit recipe"
              >
                ✏️
              </button>
              <button
                type="button"
                on:click={() => handleDelete(recipe)}
                class="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                title="Delete recipe"
              >
                🗑️
              </button>
            </div>
          </div>
          <div class="text-xs text-gray-700 bg-gray-50 rounded-lg px-3 py-2">
            {formatNutrition(recipe)} per {recipe.serving_unit}
          </div>
        </div>
      {/each}

      <button
        type="button"
        on:click={handleCreate}
        class="w-full py-4 px-4 bg-white border-2 border-gray-300 border-dashed rounded-xl text-sm font-semibold text-gray-600 hover:bg-gray-50 hover:border-primary-400 hover:text-primary-600 transition-colors"
      >
        + New Recipe
      </button>
    {/if}
  </div>
</div>
