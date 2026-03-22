<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import type { FoodSearchResultItem } from '../types/profile';
  import { searchFoods } from '../api/foods';

  export let initialQuery = '';

  const dispatch = createEventDispatcher<{ select: FoodSearchResultItem }>();

  let query = initialQuery;
  let results: FoodSearchResultItem[] = [];
  let loading = false;
  let searched = false;
  let debounceTimer: ReturnType<typeof setTimeout>;

  onMount(() => {
    if (initialQuery) {
      runSearch(initialQuery);
    }
  });

  $: if (initialQuery !== query && initialQuery) {
    query = initialQuery;
    runSearch(initialQuery);
  }

  async function runSearch(q: string) {
    if (!q.trim()) return;
    loading = true;
    searched = false;
    try {
      const res = await searchFoods(q.trim(), 20);
      results = res.results;
    } catch {
      results = [];
    } finally {
      loading = false;
      searched = true;
    }
  }

  function handleInput() {
    clearTimeout(debounceTimer);
    if (!query.trim()) {
      results = [];
      searched = false;
      return;
    }
    debounceTimer = setTimeout(() => runSearch(query), 400);
  }

  function handleKey(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      clearTimeout(debounceTimer);
      runSearch(query);
    }
  }
</script>

<div>
  <!-- Search input -->
  <div class="relative">
    <div class="absolute inset-y-0 left-3 flex items-center pointer-events-none">
      <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    </div>
    <input
      type="search"
      bind:value={query}
      on:input={handleInput}
      on:keydown={handleKey}
      placeholder="Search USDA database..."
      class="w-full pl-9 pr-4 py-2.5 border border-gray-300 rounded-xl bg-gray-50 focus:bg-white focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm"
      autocomplete="off"
    />
  </div>

  <!-- Loading -->
  {#if loading}
    <div class="py-6 flex items-center justify-center gap-2 text-sm text-gray-400">
      <svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      Searching...
    </div>
  {:else if searched && results.length === 0}
    <div class="py-6 text-center text-sm text-gray-500">
      No results found for "<span class="font-medium">{query}</span>"
    </div>
  {:else if results.length > 0}
    <div class="mt-3 space-y-2">
      {#each results as food (food.id)}
        <div class="bg-white border border-gray-200 rounded-xl p-3 flex items-start gap-3 hover:border-primary-300 hover:bg-primary-50 transition-colors">
          <div class="flex-1 min-w-0">
            <p class="font-medium text-gray-900 text-sm leading-snug">{food.name}</p>
            {#if food.brand}
              <p class="text-xs text-gray-500 mt-0.5">{food.brand}</p>
            {/if}
            <div class="flex flex-wrap gap-2 mt-1.5 text-xs text-gray-500">
              <span>{food.serving_size} {food.unit}</span>
              {#if food.calories != null}
                <span class="text-orange-600 font-medium">{Math.round(food.calories)} kcal</span>
              {/if}
              {#if food.protein != null}
                <span>{Math.round(food.protein)}g protein</span>
              {/if}
            </div>
          </div>
          <button type="button"
            on:click={() => dispatch('select', food)}
            class="flex-shrink-0 px-3 py-1.5 bg-primary-600 text-white text-xs font-semibold rounded-lg hover:bg-primary-700 active:bg-primary-800"
          >
            Add
          </button>
        </div>
      {/each}
    </div>
  {:else if !query}
    <p class="mt-4 text-sm text-gray-400 text-center">Type to search 8,000+ USDA foods</p>
  {/if}
</div>
