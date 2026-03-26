<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { apiRequest } from '../api/client';

  export let initialName = '';

  const dispatch = createEventDispatcher<{ created: any; cancel: void }>();

  let formData = {
    name: initialName,
    brand: '',
    serving_size: 100,
    unit: 'g',
    custom_unit: '',
    weight_quantity: null as number | null,
    weight_unit: 'g',
    calories: 0,
    protein: 0,
    carbs: 0,
    fat: 0,
    fiber: null as number | null,
    notes: '',
  };

  const massUnits = ['g', 'oz', 'lbs'];
  $: isMassUnit = massUnits.includes(formData.unit);

  let submitting = false;
  let error: string | null = null;
  let fieldErrors: Record<string, string> = {};

  const servingUnits = [
    { value: 'g', label: 'grams (g)' },
    { value: 'oz', label: 'ounces (oz)' },
    { value: 'ml', label: 'milliliters (ml)' },
    { value: 'cup', label: 'cup' },
    { value: 'tbsp', label: 'tablespoon (tbsp)' },
    { value: 'tsp', label: 'teaspoon (tsp)' },
    { value: 'piece', label: 'piece' },
    { value: 'serving', label: 'serving' },
    { value: 'other', label: 'other (custom)' },
  ];

  function validate(): boolean {
    fieldErrors = {};
    if (!formData.name || formData.name.trim().length < 2) {
      fieldErrors.name = 'Food name must be at least 2 characters';
    }
    if (formData.serving_size <= 0) {
      fieldErrors.serving_size = 'Serving size must be > 0';
    }
    if (formData.unit === 'other' && !formData.custom_unit.trim()) {
      fieldErrors.custom_unit = 'Custom unit name is required';
    }
    if (formData.calories < 0) fieldErrors.calories = 'Cannot be negative';
    if (formData.protein < 0) fieldErrors.protein = 'Cannot be negative';
    if (formData.carbs < 0) fieldErrors.carbs = 'Cannot be negative';
    if (formData.fat < 0) fieldErrors.fat = 'Cannot be negative';
    return Object.keys(fieldErrors).length === 0;
  }

  function convertWeightToGrams(qty: number, u: string): number {
    const c: Record<string, number> = { g: 1, oz: 28.35, lbs: 453.6 };
    return qty * (c[u] || 1);
  }

  async function handleSubmit() {
    if (!validate()) return;
    submitting = true;
    error = null;
    try {
      let gram_weight: number | null = null;
      if (formData.weight_quantity !== null && !isMassUnit) {
        gram_weight = convertWeightToGrams(formData.weight_quantity, formData.weight_unit);
      }
      const payload = {
        name: formData.name.trim(),
        brand: formData.brand.trim() || null,
        serving_size: formData.serving_size,
        unit: formData.unit === 'other' ? formData.custom_unit.trim() : formData.unit,
        calories: formData.calories,
        protein: formData.protein,
        carbs: formData.carbs,
        fat: formData.fat,
        fiber: formData.fiber,
        notes: formData.notes.trim() || null,
        gram_weight,
      };
      const food = await apiRequest<any>('/foods/', { method: 'POST', body: JSON.stringify(payload) });
      dispatch('created', food);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to create food';
    } finally {
      submitting = false;
    }
  }
</script>

<div class="space-y-4">
  {#if error}
    <div class="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
  {/if}

  <div>
    <label class="block text-sm font-medium text-gray-700 mb-1">Food Name *</label>
    <input
      type="text"
      bind:value={formData.name}
      placeholder="e.g., Vanilla Yogurt"
      class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
    />
    {#if fieldErrors.name}<p class="text-xs text-red-600 mt-1">{fieldErrors.name}</p>{/if}
  </div>

  <div>
    <label class="block text-sm font-medium text-gray-700 mb-1">Brand (optional)</label>
    <input type="text" bind:value={formData.brand} placeholder="e.g., Acme Brand"
      class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500" />
  </div>

  <div class="grid grid-cols-2 gap-3">
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">Serving Size *</label>
      <input type="number" bind:value={formData.serving_size} step="0.1" min="0"
        class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500" />
      {#if fieldErrors.serving_size}<p class="text-xs text-red-600 mt-1">{fieldErrors.serving_size}</p>{/if}
    </div>
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">Unit</label>
      <select bind:value={formData.unit}
        class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500">
        {#each servingUnits as u}<option value={u.value}>{u.label}</option>{/each}
      </select>
    </div>
  </div>

  {#if formData.unit === 'other'}
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">Custom Unit Name *</label>
      <input type="text" bind:value={formData.custom_unit} placeholder="e.g., scoop, slice"
        class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500" />
      {#if fieldErrors.custom_unit}<p class="text-xs text-red-600 mt-1">{fieldErrors.custom_unit}</p>{/if}
    </div>
  {/if}

  <div>
    <label class="block text-sm font-medium text-gray-700 mb-1">Calories (per serving) *</label>
    <input type="number" bind:value={formData.calories} step="0.1" min="0"
      class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500" />
    {#if fieldErrors.calories}<p class="text-xs text-red-600 mt-1">{fieldErrors.calories}</p>{/if}
  </div>

  <div class="grid grid-cols-3 gap-3">
    {#each [['protein', 'Protein (g)'], ['carbs', 'Carbs (g)'], ['fat', 'Fat (g)']] as [field, label]}
      <div>
        <label class="block text-xs font-medium text-gray-600 mb-1">{label}</label>
        <input type="number" bind:value={formData[field]} step="0.1" min="0"
          class="w-full px-2 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm" />
        {#if fieldErrors[field]}<p class="text-xs text-red-600 mt-1">{fieldErrors[field]}</p>{/if}
      </div>
    {/each}
  </div>

  <div>
    <label class="block text-xs font-medium text-gray-600 mb-1">Fiber (g, optional)</label>
    <input type="number" bind:value={formData.fiber} step="0.1" min="0"
      class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm" />
  </div>

  <div class="flex gap-2 pt-2">
    <button
      type="button"
      on:click={() => dispatch('cancel')}
      class="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg hover:bg-gray-50 text-gray-700 font-medium"
      disabled={submitting}
    >
      Cancel
    </button>
    <button
      type="button"
      on:click={handleSubmit}
      disabled={submitting}
      class="flex-1 px-4 py-2.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-300 font-medium flex items-center justify-center gap-2"
    >
      {#if submitting}
        <svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        Creating...
      {:else}
        Create Food
      {/if}
    </button>
  </div>
</div>
