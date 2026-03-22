<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { DailyLogEntry } from '../types/profile';
  import { STANDARD_MEALS } from '../types/profile';
  import { apiRequest } from '../api/client';

  export let entry: DailyLogEntry | null = null;
  export let visible = false;

  const dispatch = createEventDispatcher<{
    save: { logId: number; quantity: number; unit: string; meal_id: number | null };
    delete: number;
    close: void;
  }>();

  let quantity = 1;
  let unit = '';
  let meal_id: number | null = null;
  let portions: { description: string; gram_weight: number }[] = [];
  let lastFoodId = -1;
  let calPerGram = 0; // calories per gram of this food

  $: if (visible && entry && entry.food_id !== lastFoodId) {
    lastFoodId = entry.food_id;
    quantity = entry.quantity;
    unit = entry.unit || '';
    meal_id = null;
    calPerGram = 0;
    loadPortions(entry.food_id);
  }

  $: selectedPortion = portions.find(p => p.description === unit);
  $: estimatedCal = calPerGram > 0 && selectedPortion
    ? Math.round(calPerGram * selectedPortion.gram_weight * quantity)
    : calPerGram > 0 && unit === 'grams'
      ? Math.round(calPerGram * quantity)
      : entry && entry.calories != null
        ? Math.round((entry.calories / entry.quantity) * quantity)
        : null;

  async function loadPortions(foodId: number) {
    try {
      const [portionData, foodData] = await Promise.all([
        apiRequest(`/foods/${foodId}/portions`) as Promise<{ description: string; gram_weight: number }[]>,
        apiRequest(`/foods/${foodId}`) as Promise<any>,
      ]);
      portions = portionData;
      
      // Calculate cal/gram from food's energy nutrient and serving size
      if (foodData.food_nutrients && foodData.serving_size) {
        const energy = foodData.food_nutrients.find((n: any) => 
          n.nutrient?.name?.toLowerCase() === 'energy'
        );
        if (energy) {
          let kcal = energy.amount_per_serving;
          calPerGram = kcal / (foodData.created_by_user_id ? (foodData.serving_size || 100) : 100);
        }
      }
    } catch {
      portions = [];
    }
  }

  function handleSave() {
    if (!entry) return;
    dispatch('save', { logId: entry.id, quantity, unit, meal_id });
  }

  function close() {
    lastFoodId = -1;
    dispatch('close');
  }
</script>

{#if visible && entry}
  <div
    class="fixed inset-0 bg-black bg-opacity-40 z-40"
    on:click={close}
    on:keydown={(e) => e.key === 'Escape' && close()}
    role="button" tabindex="-1" aria-label="Close"
  ></div>

  <div class="fixed bottom-0 left-0 right-0 bg-white rounded-t-2xl shadow-xl z-50 pb-safe max-h-[80vh] overflow-y-auto">
    <div class="flex justify-center pt-3 pb-1">
      <div class="w-10 h-1 bg-gray-300 rounded-full"></div>
    </div>

    <div class="px-4 py-3 border-b border-gray-100">
      <h3 class="font-semibold text-gray-900 text-lg">Edit Log</h3>
      <p class="text-sm text-gray-500 mt-0.5">{entry.food_name}</p>
    </div>

    <div class="px-4 py-4 space-y-4">
      <!-- Unit selector -->
      <div>
        <label class="block text-xs font-medium text-gray-600 mb-1.5" for="edit-unit">Unit / Portion</label>
        {#if portions.length > 0}
          <select
            id="edit-unit"
            bind:value={unit}
            class="w-full px-3 py-2.5 border border-gray-300 rounded-xl text-sm bg-white"
          >
            {#each portions as p}
              <option value={p.description}>{p.description}</option>
            {/each}
            <option value="grams">grams</option>
          </select>
        {:else}
          <input
            id="edit-unit"
            type="text"
            bind:value={unit}
            class="w-full px-3 py-2.5 border border-gray-300 rounded-xl text-sm"
            placeholder="e.g. cup, medium, slice"
          />
        {/if}
      </div>

      <!-- Quantity -->
      <div>
        <label class="block text-xs font-medium text-gray-600 mb-1.5" for="edit-qty">
          Quantity {#if unit === 'grams'}(g){/if}
        </label>
        <input
          id="edit-qty"
          type="number"
          bind:value={quantity}
          min="0.01"
          step="any"
          class="w-full px-3 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-center text-lg font-medium"
        />
      </div>

      {#if estimatedCal != null}
        <p class="text-center text-sm text-gray-500">
          ≈ <span class="font-semibold text-orange-600">{estimatedCal} kcal</span>
        </p>
      {/if}

      <!-- Meal -->
      <div>
        <label class="block text-xs font-medium text-gray-600 mb-1.5">Meal <span class="text-gray-400 font-normal">(optional)</span></label>
        <div class="grid grid-cols-4 gap-2">
          {#each STANDARD_MEALS as meal}
            <button type="button"
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

    <div class="px-4 pb-6 flex gap-3">
      <button type="button"
        on:click={() => { close(); dispatch('delete', entry.id); }}
        class="py-3 px-4 border border-red-300 rounded-xl font-medium text-red-600 hover:bg-red-50"
      >
        Delete
      </button>
      <button type="button"
        on:click={close}
        class="flex-1 py-3 border border-gray-300 rounded-xl font-medium text-gray-700 hover:bg-gray-50"
      >
        Cancel
      </button>
      <button type="button"
        on:click={handleSave}
        disabled={quantity <= 0}
        class="flex-1 py-3 bg-primary-600 text-white rounded-xl font-semibold hover:bg-primary-700 disabled:opacity-50"
      >
        Save
      </button>
    </div>
  </div>
{/if}
