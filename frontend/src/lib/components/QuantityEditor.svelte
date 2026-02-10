<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import type { MultiFoodItem, FoodPortion } from '../stores/multiFoodForm';

  export let item: MultiFoodItem;

  const dispatch = createEventDispatcher();

  let quantity = item.parsed_quantity;
  let unit = item.parsed_unit;
  let calculatedNutrition = {
    calories: item.calories || 0,
    protein: item.protein || 0,
    fat: item.fat || 0,
    fiber: item.fiber || 0,
    weight: 0,
  };

  // Build units list based on what portions are available
  // Mass and volume units are interconvertible within their category
  const massUnits = ['g', 'oz', 'lb', 'kg'];
  const volumeUnits = ['ml', 'tsp', 'tbsp', 'cup', 'fl oz', 'L'];
  
  // Aliases for detecting unit categories
  const massAliases = new Set(['g', 'gram', 'grams', 'oz', 'ounce', 'ounces', 'lb', 'lbs', 'pound', 'pounds', 'kg', 'kilogram', 'kilograms']);
  const volumeAliases = new Set(['ml', 'milliliter', 'tsp', 'teaspoon', 'tbsp', 'tablespoon', 'cup', 'cups', 'fl oz', 'fluid ounce', 'l', 'liter', 'litre']);
  
  $: availableUnits = getAvailableUnits(item.portions);
  
  function getAvailableUnits(portions: FoodPortion[] | undefined): string[] {
    const result: string[] = [];
    let hasMass = false;
    let hasVolume = false;
    const descriptiveUnits: string[] = [];
    
    if (portions && portions.length > 0) {
      for (const p of portions) {
        // Check both modifier and unit_name for category detection
        const modifier = (p.modifier || '').toLowerCase();
        const unitName = (p.unit_name || '').toLowerCase();
        const displayUnit = p.modifier || p.unit_name;
        
        // Check if either field indicates mass or volume
        const isMass = massAliases.has(modifier) || massAliases.has(unitName);
        const isVolume = volumeAliases.has(modifier) || volumeAliases.has(unitName);
        
        if (isMass) {
          hasMass = true;
        } else if (isVolume) {
          hasVolume = true;
        } else if (displayUnit && !descriptiveUnits.includes(displayUnit)) {
          // Descriptive unit (slice, piece, large, berries, etc.) - only include if present
          descriptiveUnits.push(displayUnit);
        }
      }
    }
    
    // Always include mass units (weight always works for food)
    result.push(...massUnits);
    
    // Include volume units if any volume portion exists
    if (hasVolume) {
      result.push(...volumeUnits);
    }
    
    // Add food-specific descriptive units at the end
    result.push(...descriptiveUnits);
    
    return result;
  }

  let debounceTimer: ReturnType<typeof setTimeout>;

  function findMatchingPortion(unitName: string): FoodPortion | null {
    if (!item.portions || item.portions.length === 0) return null;
    
    const normalized = unitName.toLowerCase();
    return item.portions.find(p => {
      const pUnit = (p.modifier || p.unit_name || '').toLowerCase();
      return pUnit === normalized || pUnit.includes(normalized) || normalized.includes(pUnit);
    }) || null;
  }

  // Unit conversion factors to grams
  const massToGrams: Record<string, number> = {
    'g': 1,
    'oz': 28.3495,
    'lb': 453.592,
    'kg': 1000,
  };
  
  // Volume conversion factors to ml (then we need density for grams)
  const volumeToMl: Record<string, number> = {
    'ml': 1,
    'tsp': 4.929,
    'tbsp': 14.787,
    'cup': 236.588,
    'fl oz': 29.574,
    'L': 1000,
  };

  function calculateNutrition() {
    if (!item.selected_food_id) {
      return;
    }

    let gramsTotal: number;
    
    // Try to find a matching portion for the selected unit
    const matchedPortion = findMatchingPortion(unit);
    
    if (matchedPortion) {
      // Use portion: quantity × (gram_weight / amount)
      const gramsPerUnit = matchedPortion.gram_weight / matchedPortion.amount;
      gramsTotal = quantity * gramsPerUnit;
    } else if (massToGrams[unit]) {
      // Direct mass conversion
      gramsTotal = quantity * massToGrams[unit];
    } else if (volumeToMl[unit]) {
      // Volume conversion - find a volume portion to get density, or approximate 1ml ≈ 1g
      const volumePortion = item.portions?.find(p => {
        const pUnit = (p.unit_name || '').toLowerCase();
        return volumeToMl[pUnit] !== undefined || ['cup', 'tbsp', 'tsp', 'ml'].some(v => pUnit.includes(v));
      });
      
      if (volumePortion) {
        // Calculate density from the portion (g/ml)
        const portionMl = volumeToMl[volumePortion.unit_name?.toLowerCase() || ''] || 236.588; // default to cup
        const density = volumePortion.gram_weight / (volumePortion.amount * portionMl);
        gramsTotal = quantity * volumeToMl[unit] * density;
      } else {
        // Approximate: 1ml ≈ 1g (water density)
        gramsTotal = quantity * volumeToMl[unit];
      }
    } else {
      // Unknown unit - treat as servings × serving_size
      gramsTotal = quantity * (item.serving_size || 100);
    }
    
    // Calculate nutrients based on grams (nutrients are per 100g in USDA data)
    const multiplier = gramsTotal / 100;
    
    calculatedNutrition = {
      calories: Math.round((item.calories || 0) * multiplier),
      protein: Math.round((item.protein || 0) * multiplier * 10) / 10,
      fat: Math.round((item.fat || 0) * multiplier * 10) / 10,
      fiber: Math.round((item.fiber || 0) * multiplier * 10) / 10,
      weight: Math.round(gramsTotal * 10) / 10,
    };
  }

  function handleQuantityChange() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      calculateNutrition();
    }, 300);
  }

  function handleSave() {
    dispatch('save', {
      parsed_quantity: quantity,
      parsed_unit: unit,
      calories: calculatedNutrition.calories,
      protein: calculatedNutrition.protein,
      fat: calculatedNutrition.fat,
      fiber: calculatedNutrition.fiber,
    });
  }

  function handleCancel() {
    dispatch('cancel');
  }

  function handleBackdropClick() {
    handleCancel();
  }

  onMount(() => {
    calculateNutrition();
  });
</script>

<div class="fixed inset-0 bg-black bg-opacity-50 flex items-end md:items-center justify-center z-50">
  <!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
  <!-- Backdrop -->
  <div 
    class="absolute inset-0" 
    on:click={handleBackdropClick}
    on:keydown={(e) => e.key === 'Escape' && handleBackdropClick()}
    role="button"
    tabindex="-1"
    aria-label="Close modal"
  ></div>

  <!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
  <!-- Modal -->
  <div
    class="relative bg-white rounded-t-lg md:rounded-lg shadow-xl w-full md:max-w-md md:mx-4 max-h-[80vh] overflow-y-auto"
    on:click|stopPropagation
    on:keydown|stopPropagation
    role="dialog"
    aria-modal="true"
    aria-labelledby="quantity-editor-title"
  >
    <!-- Header -->
    <div class="sticky top-0 bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
      <h3 id="quantity-editor-title" class="text-lg font-semibold text-gray-900">Edit Quantity</h3>
      <button
        on:click={handleCancel}
        class="text-gray-400 hover:text-gray-600"
        style="min-width: 44px; min-height: 44px;"
      >
        <svg class="w-6 h-6 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <!-- Content -->
    <div class="p-4 space-y-4">
      <!-- Food name -->
      <div>
        <div class="text-sm text-gray-600">Food</div>
        <div class="font-medium text-gray-900">{item.selected_name || 'Unknown'}</div>
      </div>

      <!-- Quantity input -->
      <div>
        <label for="quantity-input" class="block text-sm font-medium text-gray-700 mb-2">Quantity</label>
        <input
          id="quantity-input"
          type="number"
          bind:value={quantity}
          on:input={handleQuantityChange}
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-base"
          style="min-height: 44px;"
          step="0.1"
          min="0"
        />
      </div>

      <!-- Unit dropdown -->
      <div>
        <label for="unit-select" class="block text-sm font-medium text-gray-700 mb-2">Unit</label>
        <select
          id="unit-select"
          bind:value={unit}
          on:change={handleQuantityChange}
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-base"
          style="min-height: 44px;"
        >
          {#each availableUnits as unitOption}
            <option value={unitOption}>{unitOption}</option>
          {/each}
        </select>
      </div>

      <!-- Nutrition preview -->
      {#if item.selected_food_id}
        <div class="bg-gray-50 rounded-lg p-3">
          <div class="text-sm font-medium text-gray-700 mb-2">Nutrition</div>
          <div class="grid grid-cols-2 gap-2 text-sm">
            <div>
              <span class="text-gray-600">Calories:</span>
              <span class="font-medium ml-1">{calculatedNutrition.calories}</span>
            </div>
            <div>
              <span class="text-gray-600">Protein:</span>
              <span class="font-medium ml-1">{calculatedNutrition.protein}g</span>
            </div>
            <div>
              <span class="text-gray-600">Fat:</span>
              <span class="font-medium ml-1">{calculatedNutrition.fat}g</span>
            </div>
            <div>
              <span class="text-gray-600">Fiber:</span>
              <span class="font-medium ml-1">{calculatedNutrition.fiber}g</span>
            </div>
            <div class="col-span-2">
              <span class="text-gray-600">Weight:</span>
              <span class="font-medium ml-1">{calculatedNutrition.weight}g</span>
            </div>
          </div>
        </div>
      {/if}
    </div>

    <!-- Footer -->
    <div class="sticky bottom-0 bg-white border-t border-gray-200 px-4 py-3 flex gap-2">
      <button
        on:click={handleCancel}
        class="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 text-gray-700 font-medium"
        style="min-height: 44px;"
      >
        Cancel
      </button>
      <button
        on:click={handleSave}
        class="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 font-medium"
        style="min-height: 44px;"
      >
        Save
      </button>
    </div>
  </div>
</div>
