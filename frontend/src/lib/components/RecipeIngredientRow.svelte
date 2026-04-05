<script lang="ts">
  import { createEventDispatcher, onDestroy } from 'svelte';
  import { searchProfileFoods } from '../api/profile';
  import { searchFoods, type SummaryNutrient } from '../api/foods';
  import type { FoodSearchResultItem } from '../types/profile';
  import { apiRequest } from '../api/client';
  import { parseFraction } from '../utils/parseFraction';
  import { buildPortionOptionsFromApi, type PortionOption } from '../utils/portionOptions';
  import { createNutritionPreview } from '../utils/nutritionPreview';
  import FractionInput from './FractionInput.svelte';
  import NutrientBadges from './NutrientBadges.svelte';

  export let ingredient: {
    food_id?: number;
    food_name?: string;
    quantity?: number;
    unit?: string;
    portion_description?: string;
    searchText?: string;
    summaryNutrients?: SummaryNutrient[] | null;
  } | null = null;
  export let state: 'editing' | 'locked' = 'editing';
  export let recipeId: number | null = null;

  const dispatch = createEventDispatcher<{
    lock: {
      food_id: number;
      food_name: string;
      quantity: number;
      unit: string;
      portion_description: string;
      summaryNutrients: SummaryNutrient[] | null;
    };
    unlock: void;
    remove: void;
    addFood: void;
  }>();

  // Editing state
  let searchQuery = ingredient?.searchText || '';
  let searchResults: FoodSearchResultItem[] = [];
  let searching = false;
  let debounceTimer: ReturnType<typeof setTimeout>;
  let selectedFood: FoodSearchResultItem | null = null;
  let portions: PortionOption[] = [];
  let quantityStr = ingredient?.quantity != null ? String(ingredient.quantity) : '1';
  $: quantity = parseFraction(quantityStr) ?? 0;
  let selectedPortionIndex = 0;

  // Nutrition preview (shared with QuickLogSheet / EditLogSheet)
  const { nutrients: previewStore, update: updatePreview, clear: clearPreview, destroy: destroyPreview } = createNutritionPreview();
  $: previewNutrients = $previewStore;

  $: estGrams = (() => {
    if (!selectedFood || !portions[selectedPortionIndex]) return 0;
    return quantity * portions[selectedPortionIndex].gram_weight;
  })();

  $: if (selectedFood && estGrams > 0) {
    updatePreview(selectedFood.id, estGrams);
  }

  onDestroy(destroyPreview);

  async function handleSearch() {
    if (!searchQuery.trim()) {
      searchResults = [];
      return;
    }
    searching = true;
    try {
      // Search profile foods first (server-side filtered)
      const profileResults = await searchProfileFoods(searchQuery, 10);

      // Map profile foods to FoodSearchResultItem format with ★ prefix
      const profileItems: FoodSearchResultItem[] = profileResults.map(uf => ({
        id: uf.food.id,
        name: `★ ${uf.food.name}`,
        brand: uf.food.brand,
        serving_size: uf.food.serving_size,
        unit: uf.food.unit,
        usda_fdc_id: null,
        similarity: null,
        calories: uf.food.calories,
        protein: uf.food.protein,
        carbs: uf.food.carbs,
        fat: uf.food.fat,
        portions: uf.food.portions,
      }));

      // Also search USDA
      const usdaRes = await searchFoods(searchQuery, 5);

      // Combine: profile first, then USDA (avoid duplicates)
      const combined = [...profileItems];
      for (const r of usdaRes.results) {
        if (!combined.find(c => c.id === r.id)) {
          combined.push(r);
        }
      }
      searchResults = combined.slice(0, 15);
    } catch {
      searchResults = [];
    } finally {
      searching = false;
    }
  }

  function onSearchInput() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(handleSearch, 300);
  }

  async function selectFood(food: FoodSearchResultItem) {
    // Store the food with original name (without ★ prefix)
    const cleanName = food.name.replace(/^★\s+/, '');
    selectedFood = { ...food, name: cleanName };
    searchResults = [];
    searchQuery = cleanName;
    clearPreview();

    // Fetch portions and build options via shared utility
    try {
      const rawPortions = await apiRequest<{description: string; gram_weight: number}[]>(`/foods/${food.id}/portions`);
      portions = buildPortionOptionsFromApi(rawPortions);

      // Set quantity from first portion's default
      selectedPortionIndex = 0;
      if (portions.length > 0) {
        quantityStr = String(portions[0].default_qty);
      }
    } catch {
      portions = [];
    }
  }

  function onPortionChange() {
    const opt = portions[selectedPortionIndex];
    if (opt) quantityStr = String(opt.default_qty);
  }

  function handleLock() {
    if (!selectedFood || quantity <= 0 || portions.length === 0) return;
    const portion = portions[selectedPortionIndex];
    dispatch('lock', {
      food_id: selectedFood.id,
      food_name: selectedFood.name,
      quantity: quantity,
      unit: portion.label,
      portion_description: portion.label,
      summaryNutrients: previewNutrients,
    });
  }

  function handleUnlock() {
    dispatch('unlock');
  }

  function handleRemove() {
    dispatch('remove');
  }
</script>

{#if state === 'editing'}
  <div class="bg-white border border-gray-200 rounded-xl p-4 space-y-3">
    <!-- Search input -->
    <div class="relative">
      <input
        type="text"
        bind:value={searchQuery}
        on:input={onSearchInput}
        placeholder="Search for food..."
        class="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-600"
      />
      {#if searching}
        <div class="absolute right-3 top-2.5 text-gray-400 text-sm">Searching...</div>
      {/if}
    </div>

    <!-- Search results dropdown -->
    {#if searchResults.length > 0}
      <div class="border border-gray-200 rounded-lg max-h-48 overflow-y-auto">
        {#each searchResults as result}
          <button
            type="button"
            on:click={() => selectFood(result)}
            class="w-full px-3 py-2 text-left hover:bg-gray-50 flex justify-between items-center border-b border-gray-100 last:border-b-0"
          >
            <span class="text-sm text-gray-900">{result.name}</span>
            {#if result.calories}
              <span class="text-xs text-gray-500">{Math.round(result.calories)} kcal</span>
            {/if}
          </button>
        {/each}
      </div>
    {/if}

    <!-- Quantity & portion inputs (shown after food selected) -->
    {#if selectedFood && portions.length > 0}
      <div class="flex gap-2 items-end">
        <div class="flex-1 min-w-0">
          <label class="block text-xs font-medium text-gray-600 mb-1">Qty</label>
          <FractionInput bind:value={quantityStr} />
        </div>
        <div class="flex-1 min-w-0">
          <label class="block text-xs font-medium text-gray-600 mb-1" for="ingredient-unit">Unit</label>
          <select
            id="ingredient-unit"
            bind:value={selectedPortionIndex}
            on:change={onPortionChange}
            class="w-full px-3 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-600"
          >
            {#each portions as p, i}
              <option value={i}>{p.label}</option>
            {/each}
          </select>
        </div>
        <button
          type="button"
          on:click={handleLock}
          disabled={quantity <= 0}
          class="px-4 py-2.5 bg-green-600 text-white rounded-xl text-sm font-semibold hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
        >
          ✓
        </button>
      </div>

      <!-- Nutrition preview -->
      {#if previewNutrients && previewNutrients.length > 0}
        <div class="text-center text-sm text-gray-500">
          ≈ <NutrientBadges summaryNutrients={previewNutrients} size="sm" />
        </div>
      {/if}
    {/if}

    <!-- Remove button -->
    <div class="flex justify-end">
      <button
        type="button"
        on:click={handleRemove}
        class="text-xs text-red-600 hover:text-red-700"
      >
        Remove
      </button>
    </div>
  </div>
{:else}
  <!-- Locked state -->
  <div class="bg-gray-50 border border-gray-200 rounded-xl p-4 flex items-center justify-between">
    <div class="flex-1 min-w-0">
      <p class="text-sm font-semibold text-gray-900">{ingredient?.food_name || 'Unknown'}</p>
      <p class="text-xs text-gray-600">
        {ingredient?.quantity} {ingredient?.unit}
      </p>
      {#if ingredient?.summaryNutrients && ingredient.summaryNutrients.length > 0}
        <div class="mt-1">
          <NutrientBadges summaryNutrients={ingredient.summaryNutrients} size="xs" />
        </div>
      {/if}
    </div>
    <div class="flex gap-2">
      <button
        type="button"
        on:click={handleUnlock}
        class="p-2 text-gray-600 hover:text-gray-900"
        title="Edit"
      >
        ✏️
      </button>
      <button
        type="button"
        on:click={handleRemove}
        class="p-2 text-red-600 hover:text-red-700"
        title="Remove"
      >
        🗑️
      </button>
    </div>
  </div>
{/if}
