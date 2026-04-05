<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { UserFood } from '../types/profile';
  import { getDisplayName, getFoodCalPerGram, STANDARD_MEALS } from '../types/profile';
  import { parseFraction } from '../utils/parseFraction';
  import { buildPortionOptions, type PortionOption } from '../utils/portionOptions';
  import { createNutritionPreview } from '../utils/nutritionPreview';
  import FractionInput from './FractionInput.svelte';
  import NutrientBadges from './NutrientBadges.svelte';

  export let userFood: UserFood | null = null;
  export let visible = false;

  const dispatch = createEventDispatcher<{
    log: { quantity: number; unit: string; meal_id: number | null };
    close: void;
  }>();

  let quantityStr = '1';
  $: quantity = parseFraction(quantityStr) ?? 1;
  let selectedPortionIndex = 0;
  let meal_id: number | null = null;
  let submitting = false;
  let lastUserFoodId: number | null = null;

  let portionOptions: PortionOption[] = [];

  $: if (userFood) {
    portionOptions = buildPortionOptions(userFood.food.portions ?? []);
  }

  $: if (visible && userFood && userFood.id !== lastUserFoodId) {
    lastUserFoodId = userFood.id;
    meal_id = userFood.default_meal_id ?? null;

    // Try to match the user's saved default_unit to a portion option
    const savedUnit = userFood.default_unit;
    if (savedUnit) {
      const matchIdx = portionOptions.findIndex(o => o.label === savedUnit);
      if (matchIdx >= 0) {
        selectedPortionIndex = matchIdx;
        quantityStr = String(userFood.default_quantity ?? portionOptions[matchIdx].default_qty);
      } else {
        selectedPortionIndex = 0;
        quantityStr = String(userFood.default_quantity ?? portionOptions[0]?.default_qty ?? 1);
      }
    } else {
      selectedPortionIndex = 0;
      quantityStr = String(userFood.default_quantity ?? portionOptions[0]?.default_qty ?? 1);
    }
  }

  $: displayName = userFood ? getDisplayName(userFood) : '';
  $: calPerGram = userFood ? getFoodCalPerGram(userFood.food) : null;

  // Compute summary nutrients server-side (same logic as daily log view)
  $: estGrams = (() => {
    if (!userFood || !portionOptions[selectedPortionIndex]) return 0;
    return quantity * portionOptions[selectedPortionIndex].gram_weight;
  })();

  const { nutrients: summaryNutrientsStore, update: updatePreview } = createNutritionPreview();
  $: summaryNutrients = $summaryNutrientsStore;

  $: if (userFood && estGrams > 0) {
    updatePreview(userFood.food.id, estGrams);
  }

  function onPortionChange() {
    const opt = portionOptions[selectedPortionIndex];
    if (opt) quantityStr = String(opt.default_qty);
  }

  function close() {
    dispatch('close');
  }

  function handleLog() {
    if (submitting || !userFood) return;
    const selected = portionOptions[selectedPortionIndex];
    dispatch('log', { quantity, unit: selected?.label ?? 'g', meal_id });
  }
</script>

{#if visible}
  <!-- Backdrop -->
  <div
    class="fixed inset-0 bg-black bg-opacity-40 z-40"
    on:click={close}
    on:keydown={(e) => e.key === 'Escape' && close()}
    role="button"
    tabindex="-1"
    aria-label="Close"
  ></div>

  <!-- Sheet -->
  <div class="fixed bottom-0 left-0 right-0 bg-white rounded-t-2xl shadow-xl z-50 pb-safe">
    <!-- Handle -->
    <div class="flex justify-center pt-3 pb-1">
      <div class="w-10 h-1 bg-gray-300 rounded-full"></div>
    </div>

    <!-- Header -->
    <div class="px-4 py-3 border-b border-gray-100">
      <h3 class="font-semibold text-gray-900 text-lg">{displayName}</h3>
      {#if userFood}
        <p class="text-sm text-gray-500 mt-0.5">
          {userFood.food.name}
          {#if userFood.food.brand} · {userFood.food.brand}{/if}
        </p>
      {/if}
    </div>

    <!-- Form -->
    <div class="px-4 py-4 space-y-4">
      <!-- Quantity + Unit -->
      <div class="flex gap-3">
        <div class="flex-1 min-w-0">
          <label class="block text-xs font-medium text-gray-600 mb-1.5">Qty</label>
          <FractionInput bind:value={quantityStr} />
        </div>
        <div class="flex-1 min-w-0">
          <label class="block text-xs font-medium text-gray-600 mb-1.5" for="log-unit">Unit</label>
          <select
            id="log-unit"
            bind:value={selectedPortionIndex}
            on:change={onPortionChange}
            class="w-full px-3 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          >
            {#each portionOptions as opt, i}
              <option value={i}>{opt.label}</option>
            {/each}
          </select>
        </div>
      </div>

      <!-- Estimated nutrients (server-computed, same as daily view) -->
      {#if summaryNutrients && summaryNutrients.length > 0}
        <div class="text-center text-sm text-gray-500">
          ≈ <NutrientBadges summaryNutrients={summaryNutrients} size="sm" />
        </div>
      {/if}

      <!-- Meal -->
      <div>
        <label class="block text-xs font-medium text-gray-600 mb-1.5">Meal <span class="text-gray-400 font-normal">(optional)</span></label>
        <div class="grid grid-cols-4 gap-2">
          {#each STANDARD_MEALS as meal}
            <button
              type="button"
              on:click={() => meal_id = meal_id === meal.id ? null : meal.id}
              class="py-2 px-1 text-xs rounded-xl border-2 font-medium transition-colors
                {meal_id === meal.id
                  ? 'border-primary-500 bg-primary-50 text-primary-700'
                  : 'border-gray-200 text-gray-600 hover:border-gray-300'}"
            >
              {meal.name}
            </button>
          {/each}
        </div>
      </div>
    </div>

    <!-- Actions -->
    <div class="px-4 pb-6 flex gap-3">
      <button
        type="button"
        on:click={close}
        class="flex-1 py-3 border border-gray-300 rounded-xl font-medium text-gray-700 hover:bg-gray-50"
      >
        Cancel
      </button>
      <button
        type="button"
        on:click={handleLog}
        disabled={submitting || quantity <= 0}
        class="px-6 py-3 bg-primary-600 text-white rounded-xl font-semibold hover:bg-primary-700 active:bg-primary-800 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        style="flex: 2"
      >
        {#if submitting}
          Logging...
        {:else}
          Log Food
        {/if}
      </button>
    </div>
  </div>
{/if}
