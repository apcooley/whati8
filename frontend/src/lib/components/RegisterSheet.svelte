<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { FoodSearchResultItem } from '../types/profile';
  import { STANDARD_MEALS } from '../types/profile';
  import { parseFraction } from '../utils/parseFraction';
  import FractionInput from './FractionInput.svelte';

  export let food: FoodSearchResultItem | null = null;
  export let visible = false;

  const dispatch = createEventDispatcher<{
    register: {
      food_id: number;
      nickname: string | null;
      default_quantity: number | null;
      default_unit: string | null;
      default_meal_id: number | null;
      is_favorite: boolean;
    };
    close: void;
  }>();

  let nickname = '';
  let quantityStr = '';
  $: default_quantity = parseFraction(quantityStr);
  let selectedPortionIndex = 0;
  let default_meal_id: number | null = null;
  let is_favorite = false;
  let submitting = false;
  let lastFoodId: number | null = null;

  interface PortionOption {
    label: string;
    gram_weight: number;
    default_qty: number;
  }

  let portionOptions: PortionOption[] = [];

  // Junk modifiers to skip entirely
  const SKIP_MODIFIERS = ['nlea serving', 'quantity not specified'];

  $: if (food) {
    const opts: PortionOption[] = [];

    if (food.portions && food.portions.length > 0) {
      for (const p of food.portions) {
        const mod = (p.modifier ?? '').toLowerCase();
        const unit = (p.unit_name ?? '').toLowerCase();

        // Skip junk portions
        if (SKIP_MODIFIERS.some(s => mod.includes(s))) continue;

        // Build a human-readable label
        let label: string;
        if (p.modifier && unit !== 'undetermined') {
          label = `${p.modifier} (${Math.round(p.gram_weight)}g)`;
        } else if (p.modifier) {
          label = `${p.modifier} (${Math.round(p.gram_weight)}g)`;
        } else if (unit !== 'undetermined') {
          label = `${p.unit_name} (${Math.round(p.gram_weight)}g)`;
        } else {
          // Both modifier and unit_name are useless — skip
          continue;
        }

        opts.push({ label, gram_weight: p.gram_weight, default_qty: p.amount });
      }
    }

    // Always add grams and oz as fallback at the end
    opts.push({ label: 'grams', gram_weight: 1, default_qty: food.serving_size || 100 });
    if (!opts.some(o => o.label.toLowerCase().startsWith('oz'))) opts.push({ label: 'oz', gram_weight: 28.35, default_qty: 1 });

    portionOptions = opts;
  }

  // Reset form when sheet opens
  $: if (visible && food && portionOptions.length > 0 && food.id !== lastFoodId) {
    lastFoodId = food.id;
    nickname = '';
    selectedPortionIndex = 0;
    quantityStr = String(portionOptions[0]?.default_qty ?? 1);
    default_meal_id = null;
    is_favorite = false;
  }

  // When portion selection changes, update quantity
  function onPortionChange() {
    const opt = portionOptions[selectedPortionIndex];
    if (opt) quantityStr = String(opt.default_qty);
  }

  function close() {
    dispatch('close');
  }

  function handleRegister() {
    if (!food || submitting) return;
    const selected = portionOptions[selectedPortionIndex];
    dispatch('register', {
      food_id: food.id,
      nickname: nickname.trim() || null,
      default_quantity,
      default_unit: selected?.label ?? 'g',
      default_meal_id,
      is_favorite,
    });
  }
</script>

{#if visible && food}
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
  <div class="fixed bottom-0 left-0 right-0 bg-white rounded-t-2xl shadow-xl z-50 pb-safe max-h-[85vh] overflow-y-auto">
    <!-- Handle -->
    <div class="flex justify-center pt-3 pb-1">
      <div class="w-10 h-1 bg-gray-300 rounded-full"></div>
    </div>

    <!-- Header -->
    <div class="px-4 py-3 border-b border-gray-100">
      <h3 class="font-semibold text-gray-900">Add to Your Foods</h3>
      <p class="text-sm text-gray-500 mt-0.5 truncate">
        {food.name}{#if food.brand} · {food.brand}{/if}
      </p>
      {#if food.calories != null}
        <p class="text-xs text-gray-400 mt-0.5">{food.calories} kcal / 100g</p>
      {/if}
    </div>

    <!-- Form -->
    <div class="px-4 py-4 space-y-4">
      <!-- Nickname -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1.5" for="register-nickname">
          Nickname <span class="text-gray-400 font-normal">(optional)</span>
        </label>
        <input
          id="register-nickname"
          type="text"
          bind:value={nickname}
          placeholder="{food.name}"
          class="w-full px-3 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
        />
      </div>

      <!-- Default serving -->
      <div class="flex gap-3">
        <div class="flex-1 min-w-0">
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Qty</label>
          <FractionInput bind:value={quantityStr} />
        </div>
        <div class="flex-1">
          <label class="block text-sm font-medium text-gray-700 mb-1.5" for="register-unit">Unit</label>
          <select
            id="register-unit"
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

      <!-- Default meal -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1.5">
          Default meal <span class="text-gray-400 font-normal">(optional)</span>
        </label>
        <div class="grid grid-cols-4 gap-2">
          {#each STANDARD_MEALS as meal}
            <button
              type="button"
              on:click={() => default_meal_id = default_meal_id === meal.id ? null : meal.id}
              class="py-2 px-1 text-xs rounded-xl border-2 font-medium transition-colors
                {default_meal_id === meal.id
                  ? 'border-primary-500 bg-primary-50 text-primary-700'
                  : 'border-gray-200 text-gray-600 hover:border-gray-300'}"
            >
              {meal.name}
            </button>
          {/each}
        </div>
      </div>

      <!-- Favorite toggle -->
      <label class="flex items-center gap-3 cursor-pointer">
        <div class="relative">
          <input type="checkbox" bind:checked={is_favorite} class="sr-only" />
          <div class="w-10 h-6 rounded-full transition-colors {is_favorite ? 'bg-primary-600' : 'bg-gray-300'}"></div>
          <div class="absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow transition-transform {is_favorite ? 'translate-x-4' : ''}"></div>
        </div>
        <span class="text-sm font-medium text-gray-700">Add to Favorites ⭐</span>
      </label>
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
        on:click={handleRegister}
        disabled={submitting}
        class="px-6 py-3 bg-primary-600 text-white rounded-xl font-semibold hover:bg-primary-700 active:bg-primary-800 disabled:opacity-50"
        style="flex: 2"
      >
        {submitting ? 'Adding...' : 'Add to My Foods'}
      </button>
    </div>
  </div>
{/if}
