<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  export let initialName: string = '';
  
  const dispatch = createEventDispatcher();

  let formData = {
    name: initialName,
    brand: '',
    serving_size: 100,
    unit: 'g',
    custom_unit: '',  // For "other" option
    weight_quantity: null as number | null,  // For non-mass units
    weight_unit: 'g',  // g, oz, lbs
    calories: 0,
    protein: 0,
    carbs: 0,
    fat: 0,
    fiber: null as number | null,
    notes: '',
  };

  // Check if unit is a mass unit
  const massUnits = ['g', 'oz', 'lbs'];
  $: isMassUnit = massUnits.includes(formData.unit);

  let isSubmitting = false;
  let error: string | null = null;
  let fieldErrors: Record<string, string> = {};

  const servingUnits = [
    { value: 'g', label: 'grams (g)' },
    { value: 'oz', label: 'ounces (oz)' },
    { value: 'ml', label: 'milliliters (ml)' },
    { value: 'fl oz', label: 'fluid ounces (fl oz)' },
    { value: 'cup', label: 'cup' },
    { value: 'tbsp', label: 'tablespoon (tbsp)' },
    { value: 'tsp', label: 'teaspoon (tsp)' },
    { value: 'piece', label: 'piece' },
    { value: 'serving', label: 'serving' },
    { value: 'other', label: 'other (custom)' },
  ];

  function validateForm(): boolean {
    fieldErrors = {};
    error = null;

    if (!formData.name || formData.name.trim().length < 2) {
      fieldErrors.name = 'Food name must be at least 2 characters';
    }

    if (formData.serving_size <= 0) {
      fieldErrors.serving_size = 'Serving size must be greater than 0';
    }

    if (formData.unit === 'other' && (!formData.custom_unit || formData.custom_unit.trim().length < 1)) {
      fieldErrors.custom_unit = 'Custom unit name is required';
    }

    if (formData.calories < 0) {
      fieldErrors.calories = 'Calories cannot be negative';
    }

    if (formData.protein < 0) {
      fieldErrors.protein = 'Protein cannot be negative';
    }

    if (formData.carbs < 0) {
      fieldErrors.carbs = 'Carbs cannot be negative';
    }

    if (formData.fat < 0) {
      fieldErrors.fat = 'Fat cannot be negative';
    }

    if (formData.fiber !== null && formData.fiber < 0) {
      fieldErrors.fiber = 'Fiber cannot be negative';
    }

    // Validate weight if entered (optional, but if quantity is entered, must be > 0)
    if (formData.weight_quantity !== null && formData.weight_quantity <= 0) {
      fieldErrors.weight_quantity = 'Weight quantity must be greater than 0';
    }

    return Object.keys(fieldErrors).length === 0;
  }

  // Convert weight to grams based on unit
  function convertWeightToGrams(quantity: number, unit: string): number {
    const conversions: Record<string, number> = {
      'g': 1,
      'oz': 28.35,
      'lbs': 453.6,
    };
    return quantity * (conversions[unit] || 1);
  }

  async function handleSubmit() {
    if (!validateForm()) {
      return;
    }

    isSubmitting = true;
    error = null;

    try {
      // Calculate gram_weight if weight is provided for non-mass units
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
        gram_weight: gram_weight,  // Optional weight for non-mass units
      };

      const response = await fetch('/foods/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const data = await response.json();
        console.error('API Error Response:', data);
        throw new Error(data.detail || data.message || 'Failed to create food');
      }

      const food = await response.json();
      dispatch('created', food);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to create food';
    } finally {
      isSubmitting = false;
    }
  }

  function handleCancel() {
    dispatch('cancel');
  }
</script>

<div class="fixed inset-0 bg-black bg-opacity-50 flex items-end md:items-center justify-center z-50">
  <!-- Backdrop -->
  <div 
    class="absolute inset-0" 
    on:click={handleCancel}
    on:keydown={(e) => e.key === 'Escape' && handleCancel()}
    role="button"
    tabindex="-1"
    aria-label="Close modal"
  ></div>

  <!-- Modal -->
  <div
    class="relative bg-white rounded-t-lg md:rounded-lg shadow-xl w-full md:max-w-md md:mx-4 max-h-[90vh] overflow-y-auto"
  >
    <!-- Header -->
    <div class="sticky top-0 bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
      <h3 class="text-lg font-semibold text-gray-900">
        Create Custom Food
      </h3>
      <button
        on:click={handleCancel}
        class="text-gray-400 hover:text-gray-600"
        disabled={isSubmitting}
      >
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <!-- Content -->
    <div class="p-4 space-y-4">
      {#if error}
        <div class="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      {/if}

      <!-- Food Name -->
      <div>
        <label for="name" class="block text-sm font-medium text-gray-700 mb-1">
          Food Name *
        </label>
        <input
          id="name"
          type="text"
          bind:value={formData.name}
          placeholder="e.g., Vanilla Yogurt"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          disabled={isSubmitting}
        />
        {#if fieldErrors.name}
          <p class="text-sm text-red-600 mt-1">{fieldErrors.name}</p>
        {/if}
      </div>

      <!-- Brand -->
      <div>
        <label for="brand" class="block text-sm font-medium text-gray-700 mb-1">
          Brand (optional)
        </label>
        <input
          id="brand"
          type="text"
          bind:value={formData.brand}
          placeholder="e.g., Acme Brand"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          disabled={isSubmitting}
        />
      </div>

      <!-- Serving Size & Unit -->
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label for="serving_size" class="block text-sm font-medium text-gray-700 mb-1">
            Serving Size *
          </label>
          <input
            id="serving_size"
            type="number"
            bind:value={formData.serving_size}
            placeholder="100"
            step="0.1"
            min="0"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            disabled={isSubmitting}
          />
          {#if fieldErrors.serving_size}
            <p class="text-sm text-red-600 mt-1">{fieldErrors.serving_size}</p>
          {/if}
        </div>
        <div>
          <label for="unit" class="block text-sm font-medium text-gray-700 mb-1">
            Unit
          </label>
          <select
            id="unit"
            bind:value={formData.unit}
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            disabled={isSubmitting}
          >
            {#each servingUnits as unit}
              <option value={unit.value}>{unit.label}</option>
            {/each}
          </select>
        </div>
      </div>

      <!-- Custom Unit (if "other" is selected) -->
      {#if formData.unit === 'other'}
        <div>
          <label for="custom_unit" class="block text-sm font-medium text-gray-700 mb-1">
            Custom Unit Name * (e.g., "scoop", "slice", "bowl")
          </label>
          <input
            id="custom_unit"
            type="text"
            bind:value={formData.custom_unit}
            placeholder="e.g., scoop, slice, bowl"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            disabled={isSubmitting}
          />
          {#if fieldErrors.custom_unit}
            <p class="text-sm text-red-600 mt-1">{fieldErrors.custom_unit}</p>
          {/if}
        </div>
      {/if}

      <!-- Weight (per serving) - for non-mass units only -->
      {#if !isMassUnit}
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label for="weight_quantity" class="block text-sm font-medium text-gray-700 mb-1">
              Weight (per serving) <span class="text-gray-500 font-normal">(optional)</span>
            </label>
            <input
              id="weight_quantity"
              type="number"
              bind:value={formData.weight_quantity}
              placeholder="e.g., 50"
              step="0.1"
              min="0"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              disabled={isSubmitting}
            />
            {#if fieldErrors.weight_quantity}
              <p class="text-sm text-red-600 mt-1">{fieldErrors.weight_quantity}</p>
            {/if}
          </div>
          <div>
            <label for="weight_unit" class="block text-sm font-medium text-gray-700 mb-1">
              Unit
            </label>
            <select
              id="weight_unit"
              bind:value={formData.weight_unit}
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              disabled={isSubmitting}
            >
              <option value="g">grams (g)</option>
              <option value="oz">ounces (oz)</option>
              <option value="lbs">pounds (lbs)</option>
            </select>
          </div>
        </div>
      {/if}

      <!-- Calories -->
      <div>
        <label for="calories" class="block text-sm font-medium text-gray-700 mb-1">
          Calories (per serving) *
        </label>
        <input
          id="calories"
          type="number"
          bind:value={formData.calories}
          placeholder="0"
          step="0.1"
          min="0"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          disabled={isSubmitting}
        />
        {#if fieldErrors.calories}
          <p class="text-sm text-red-600 mt-1">{fieldErrors.calories}</p>
        {/if}
      </div>

      <!-- Macronutrients -->
      <div class="space-y-3">
        <p class="text-sm font-medium text-gray-700">Macronutrients (optional, per serving)</p>
        
        <div class="grid grid-cols-3 gap-3">
          <div>
            <label for="protein" class="block text-xs font-medium text-gray-600 mb-1">
              Protein (g)
            </label>
            <input
              id="protein"
              type="number"
              bind:value={formData.protein}
              placeholder="0"
              step="0.1"
              min="0"
              class="w-full px-2 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm"
              disabled={isSubmitting}
            />
            {#if fieldErrors.protein}
              <p class="text-xs text-red-600 mt-1">{fieldErrors.protein}</p>
            {/if}
          </div>
          <div>
            <label for="carbs" class="block text-xs font-medium text-gray-600 mb-1">
              Carbs (g)
            </label>
            <input
              id="carbs"
              type="number"
              bind:value={formData.carbs}
              placeholder="0"
              step="0.1"
              min="0"
              class="w-full px-2 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm"
              disabled={isSubmitting}
            />
            {#if fieldErrors.carbs}
              <p class="text-xs text-red-600 mt-1">{fieldErrors.carbs}</p>
            {/if}
          </div>
          <div>
            <label for="fat" class="block text-xs font-medium text-gray-600 mb-1">
              Fat (g)
            </label>
            <input
              id="fat"
              type="number"
              bind:value={formData.fat}
              placeholder="0"
              step="0.1"
              min="0"
              class="w-full px-2 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm"
              disabled={isSubmitting}
            />
            {#if fieldErrors.fat}
              <p class="text-xs text-red-600 mt-1">{fieldErrors.fat}</p>
            {/if}
          </div>
        </div>

        <div>
          <label for="fiber" class="block text-xs font-medium text-gray-600 mb-1">
            Fiber (g, optional)
          </label>
          <input
            id="fiber"
            type="number"
            bind:value={formData.fiber}
            placeholder="0"
            step="0.1"
            min="0"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm"
            disabled={isSubmitting}
          />
          {#if fieldErrors.fiber}
            <p class="text-xs text-red-600 mt-1">{fieldErrors.fiber}</p>
          {/if}
        </div>
      </div>

      <!-- Notes -->
      <div>
        <label for="notes" class="block text-sm font-medium text-gray-700 mb-1">
          Notes (optional)
        </label>
        <textarea
          id="notes"
          bind:value={formData.notes}
          placeholder="Add any additional notes..."
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          rows="3"
          disabled={isSubmitting}
        ></textarea>
      </div>

      <!-- Form Actions -->
      <div class="flex gap-2 pt-4 border-t border-gray-200">
        <button
          on:click={handleCancel}
          class="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 text-gray-700 font-medium"
          disabled={isSubmitting}
        >
          Cancel
        </button>
        <button
          on:click={handleSubmit}
          disabled={isSubmitting}
          class="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-300 disabled:cursor-not-allowed font-medium flex items-center justify-center gap-2"
        >
          {#if isSubmitting}
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
  </div>
</div>
