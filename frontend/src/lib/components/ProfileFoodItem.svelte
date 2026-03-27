<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { UserFood } from '../types/profile';
  import { getDisplayName, getServingLabel } from '../types/profile';
  import FoodSummary from './FoodSummary.svelte';

  export let userFood: UserFood;

  const dispatch = createEventDispatcher<{
    quickLog: UserFood;
    openSheet: UserFood;
    edit: UserFood;
    delete: UserFood;
  }>();

  $: displayName = getDisplayName(userFood);
  $: servingLabel = getServingLabel(userFood);

  // Calculate display portion in grams for the summary endpoint
  $: portionGrams = (() => {
    const unit = userFood.default_unit;
    if (!unit) return userFood.food.serving_size || 100;
    const portions = userFood.food.portions || [];
    for (const p of portions) {
      const desc = (p.portion_description || '').replace(/^[\d.]+ undetermined /, '');
      const norm = (s: string) => s.replace(/(\d+)\.0g\)/, '$1g)');
      if (norm(desc) === norm(unit)) return p.gram_weight * (userFood.default_quantity || 1);
    }
    if (unit.toLowerCase() === 'grams' || unit.toLowerCase() === 'g') return userFood.default_quantity || 100;
    return userFood.food.serving_size || 100;
  })();

  let showConfirm = false;
</script>

<div class="flex items-center gap-2 px-4 py-3 bg-white border-b border-gray-100 active:bg-gray-50">
  <div class="flex-1 min-w-0" role="button" tabindex="0"
    on:click={() => dispatch('openSheet', userFood)}
    on:keydown={(e) => e.key === 'Enter' && dispatch('openSheet', userFood)}>
    <div class="flex items-center gap-1.5">
      {#if userFood.is_favorite}
        <span class="text-yellow-400 text-sm">⭐</span>
      {/if}
      <p class="font-medium text-gray-900 truncate">{displayName}</p>
    </div>
    <div class="text-xs text-gray-500 mt-0.5 flex flex-wrap items-center gap-x-1">
      <span>{servingLabel}</span>
      <span>·</span>
      <FoodSummary foodId={userFood.food_id} quantity={portionGrams} />
    </div>
  </div>

  <button type="button"
    on:click|stopPropagation={() => dispatch('edit', userFood)}
    class="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full text-gray-300 hover:text-blue-500 hover:bg-blue-50 transition-colors"
    title="Edit {displayName}"
    aria-label="Edit {displayName}"
  >
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
    </svg>
  </button>

  <button type="button"
    on:click|stopPropagation={() => showConfirm = true}
    class="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full text-gray-300 hover:text-red-400 hover:bg-red-50 transition-colors"
    title="Remove from your foods"
    aria-label="Remove {displayName}"
  >
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
    </svg>
  </button>

  <button type="button"
    on:click|stopPropagation={() => dispatch('openSheet', userFood)}
    class="flex-shrink-0 w-9 h-9 flex items-center justify-center rounded-full bg-primary-600 text-white hover:bg-primary-700 active:bg-primary-800 shadow-sm"
    title="Log {displayName}"
    aria-label="Log {displayName}"
  >
    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 4v16m8-8H4" />
    </svg>
  </button>
</div>

{#if showConfirm}
  <div class="fixed inset-0 bg-black bg-opacity-40 z-50 flex items-center justify-center p-4"
    on:click={() => showConfirm = false}
    on:keydown={(e) => e.key === 'Escape' && (showConfirm = false)}
    role="button" tabindex="-1" aria-label="Close">
    <div class="bg-white rounded-2xl shadow-xl max-w-sm w-full p-6"
      on:click|stopPropagation on:keydown|stopPropagation role="dialog" aria-modal="true">
      <h3 class="text-lg font-bold text-gray-900 mb-2">Remove Food</h3>
      <p class="text-sm text-gray-600 mb-6">
        Delete <span class="font-semibold">"{displayName}"</span> from your registry? Your existing logs won't be affected.
      </p>
      <div class="flex gap-3">
        <button type="button"
          on:click={() => showConfirm = false}
          class="flex-1 py-3 border border-gray-300 rounded-xl font-medium text-gray-700 hover:bg-gray-50"
        >Cancel</button>
        <button type="button"
          on:click={() => { showConfirm = false; dispatch('delete', userFood); }}
          class="flex-1 py-3 bg-red-600 text-white rounded-xl font-semibold hover:bg-red-700 active:bg-red-800"
        >Delete</button>
      </div>
    </div>
  </div>
{/if}
