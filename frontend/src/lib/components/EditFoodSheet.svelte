<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { UserFood } from '../types/profile';
  import { STANDARD_MEALS } from '../types/profile';
  import { updateUserFood } from '../api/profile';
  import { parseFraction } from '../utils/parseFraction';
  import FractionInput from './FractionInput.svelte';
  import { toastStore } from '../stores/toast';

  export let userFood: UserFood | null = null;
  export let visible = false;

  const dispatch = createEventDispatcher<{ saved: UserFood; close: void }>();

  let nickname = '';
  let quantityStr = '';
  let selectedPortionIndex = 0;
  let mealId: number | null = null;
  let isFavorite = false;
  let saving = false;
  let lastId: number | null = null;

  interface PortionOption { label: string; gram_weight: number; default_qty: number; }
  let portionOptions: PortionOption[] = [];

  const SKIP_MODS = ['nlea serving', 'quantity not specified'];

  $: if (visible && userFood && userFood.id !== lastId) {
    lastId = userFood.id;
    nickname = userFood.nickname || '';
    isFavorite = userFood.is_favorite;
    mealId = userFood.default_meal_id;

    // Build portion options
    const opts: PortionOption[] = [];
    const food = userFood.food;
    if (food.portions?.length) {
      for (const p of food.portions) {
        const mod = (p.modifier ?? '').toLowerCase();
        const unit = (p.unit_name ?? '').toLowerCase();
        if (SKIP_MODS.some(s => mod.includes(s))) continue;
        let label: string;
        if (p.modifier && unit !== 'undetermined') label = `${p.modifier} (${Math.round(p.gram_weight)}g)`;
        else if (p.modifier) label = `${p.modifier} (${Math.round(p.gram_weight)}g)`;
        else if (unit !== 'undetermined') label = `${p.unit_name} (${Math.round(p.gram_weight)}g)`;
        else continue;
        opts.push({ label, gram_weight: p.gram_weight, default_qty: p.amount });
      }
    }
    opts.push({ label: 'grams', gram_weight: 1, default_qty: food.serving_size || 100 });
    if (!opts.some(o => o.label.toLowerCase().startsWith('oz')))
      opts.push({ label: 'oz', gram_weight: 28.35, default_qty: 1 });
    portionOptions = opts;

    // Match current default_unit to a portion option
    const curUnit = userFood.default_unit;
    const matchIdx = curUnit ? opts.findIndex(o => o.label === curUnit) : 0;
    selectedPortionIndex = matchIdx >= 0 ? matchIdx : 0;
    quantityStr = String(userFood.default_quantity ?? opts[selectedPortionIndex]?.default_qty ?? 1);
  }

  function onPortionChange() {
    const opt = portionOptions[selectedPortionIndex];
    if (opt) quantityStr = String(opt.default_qty);
  }

  async function handleSave() {
    if (!userFood) return;
    saving = true;
    try {
      const qty = parseFraction(quantityStr) ?? 1;
      const unit = portionOptions[selectedPortionIndex]?.label ?? 'g';
      const result = await updateUserFood(userFood.id, {
        nickname: nickname.trim() || null,
        default_quantity: qty,
        default_unit: unit,
        default_meal_id: mealId,
        is_favorite: isFavorite,
      });
      toastStore.success('Food updated');
      dispatch('saved', result);
      close();
    } catch (err: any) {
      toastStore.error(err?.message || 'Failed to update');
    } finally {
      saving = false;
    }
  }

  function close() {
    lastId = null;
    dispatch('close');
  }
</script>

{#if visible && userFood}
  <div class="fixed inset-0 bg-black bg-opacity-40 z-40"
    on:click={close} on:keydown={(e) => e.key === 'Escape' && close()} role="button" tabindex="-1" aria-label="Close">
  </div>

  <div class="fixed bottom-0 left-0 right-0 bg-white rounded-t-2xl shadow-xl z-50 pb-safe max-h-[85vh] overflow-y-auto">
    <div class="flex justify-center pt-3 pb-1">
      <div class="w-10 h-1 bg-gray-300 rounded-full"></div>
    </div>

    <div class="px-4 py-3 border-b border-gray-100">
      <h3 class="font-semibold text-gray-900 text-lg">Edit Food</h3>
      <p class="text-sm text-gray-500 mt-0.5">{userFood.food.name}</p>
    </div>

    <div class="px-4 py-4 space-y-4">
      <!-- Nickname -->
      <div>
        <label class="block text-xs font-medium text-gray-600 mb-1.5">Nickname <span class="text-gray-400">(optional)</span></label>
        <input type="text" bind:value={nickname} placeholder={userFood.food.name}
          class="w-full px-3 py-2.5 border border-gray-300 rounded-xl text-sm" />
      </div>

      <!-- Default serving -->
      <div class="flex gap-3">
        <div class="flex-1 min-w-0">
          <label class="block text-xs font-medium text-gray-600 mb-1.5">Default Qty</label>
          <FractionInput bind:value={quantityStr} />
        </div>
        <div class="flex-1 min-w-0">
          <label class="block text-xs font-medium text-gray-600 mb-1.5">Default Unit</label>
          <select bind:value={selectedPortionIndex} on:change={onPortionChange}
            class="w-full px-3 py-2.5 border border-gray-300 rounded-xl text-sm">
            {#each portionOptions as opt, i}
              <option value={i}>{opt.label}</option>
            {/each}
          </select>
        </div>
      </div>

      <!-- Default meal -->
      <div>
        <label class="block text-xs font-medium text-gray-600 mb-1.5">Default Meal</label>
        <div class="grid grid-cols-4 gap-2">
          {#each STANDARD_MEALS as meal}
            <button type="button"
              on:click={() => mealId = mealId === meal.id ? null : meal.id}
              class="py-2 px-1 text-xs rounded-xl border-2 font-medium transition-colors
                {mealId === meal.id ? 'border-primary-500 bg-primary-50 text-primary-700' : 'border-gray-200 text-gray-600 hover:border-gray-300'}"
            >{meal.name}</button>
          {/each}
        </div>
      </div>

      <!-- Favorite -->
      <label class="flex items-center gap-3 cursor-pointer">
        <input type="checkbox" bind:checked={isFavorite}
          class="w-5 h-5 rounded border-gray-300 text-primary-600 focus:ring-primary-500" />
        <span class="text-sm text-gray-700">⭐ Favorite</span>
      </label>
    </div>

    <div class="px-4 pb-6 flex gap-3">
      <button type="button" on:click={close}
        class="flex-1 py-3 border border-gray-300 rounded-xl font-medium text-gray-700 hover:bg-gray-50">Cancel</button>
      <button type="button" on:click={handleSave} disabled={saving}
        class="flex-1 py-3 bg-primary-600 text-white rounded-xl font-semibold hover:bg-primary-700 disabled:opacity-50">
        {saving ? 'Saving...' : 'Save'}
      </button>
    </div>
  </div>
{/if}
