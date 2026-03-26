<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { MealGroup } from '../types/profile';
  import { STANDARD_MEALS } from '../types/profile';
  import { copyMeal } from '../api/daily';
  import { toastStore } from '../stores/toast';

  export let sourceDate: string = '';
  export let mealGroup: MealGroup | null = null;
  export let visible = false;

  const dispatch = createEventDispatcher<{ done: void; close: void }>();

  let targetDate = '';
  let targetMealId: number | null = null;
  let lastOpened = false;

  // Initialize defaults only on open (not on every reactive cycle)
  $: if (visible && mealGroup && !lastOpened) {
    lastOpened = true;
    const today = new Date();
    targetDate = today.toISOString().split('T')[0];
    targetMealId = null;
  } else if (!visible) {
    lastOpened = false;
  }

  async function handleSubmit() {
    if (!mealGroup || !targetDate || !sourceDate) return;

    try {
      await copyMeal(sourceDate, mealGroup.meal.id, targetDate, targetMealId ?? undefined);
      toastStore.success(`${mealGroup.meal.name} copied`);
      dispatch('done');
      close();
    } catch (err) {
      toastStore.error(err instanceof Error ? err.message : 'Failed to copy meal');
    }
  }

  function close() {
    dispatch('close');
  }
</script>

{#if visible && mealGroup}
  <div
    class="fixed inset-0 bg-black bg-opacity-40 z-40"
    on:click={close}
    on:keydown={(e) => e.key === 'Escape' && close()}
    role="button" tabindex="-1" aria-label="Close"
  ></div>

  <div class="fixed bottom-0 left-0 right-0 bg-white rounded-t-2xl shadow-xl z-50 pb-safe">
    <div class="flex justify-center pt-3 pb-1">
      <div class="w-10 h-1 bg-gray-300 rounded-full"></div>
    </div>

    <div class="px-4 py-3 border-b border-gray-100">
      <h3 class="font-semibold text-gray-900 text-lg">Copy meal to...</h3>
      <p class="text-sm text-gray-500 mt-0.5">
        {mealGroup.meal.name} ({mealGroup.logs.length} {mealGroup.logs.length === 1 ? 'item' : 'items'})
      </p>
    </div>

    <div class="px-4 py-4 space-y-4">
      <!-- Date input -->
      <div>
        <label class="block text-xs font-medium text-gray-600 mb-1.5" for="target-date-meal">
          Date
        </label>
        <input
          id="target-date-meal"
          type="date"
          bind:value={targetDate}
          class="w-full px-3 py-2.5 border border-gray-300 rounded-xl text-sm"
          required
        />
      </div>

      <!-- Target meal selector -->
      <div>
        <label class="block text-xs font-medium text-gray-600 mb-1.5">
          Target Meal <span class="text-gray-400 font-normal">(defaults to {mealGroup.meal.name})</span>
        </label>
        <div class="grid grid-cols-4 gap-2">
          {#each STANDARD_MEALS as meal}
            <button type="button"
              on:click={() => targetMealId = targetMealId === meal.id ? null : meal.id}
              class="py-2 px-1 text-xs rounded-xl border-2 font-medium transition-colors
                {targetMealId === meal.id
                  ? 'border-primary-500 bg-primary-50 text-primary-700'
                  : 'border-gray-200 text-gray-600 hover:border-gray-300'}"
            >
              {meal.name}
            </button>
          {/each}
        </div>
      </div>
    </div>

    <div class="px-4 pb-6 flex gap-3">
      <button type="button"
        on:click={close}
        class="flex-1 py-3 border border-gray-300 rounded-xl font-medium text-gray-700 hover:bg-gray-50"
      >
        Cancel
      </button>
      <button type="button"
        on:click={handleSubmit}
        disabled={!targetDate}
        class="flex-1 py-3 bg-primary-600 text-white rounded-xl font-semibold hover:bg-primary-700 disabled:opacity-50"
      >
        Copy Meal
      </button>
    </div>
  </div>
{/if}
