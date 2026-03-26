<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import { multiFoodFormStore } from '../stores/multiFoodForm';
  import type { MultiFoodItem } from '../stores/multiFoodForm';
  import FoodRow from './FoodRow.svelte';
  import MealSelector from './MealSelector.svelte';
  import InlineAddFood from './InlineAddFood.svelte';

  const dispatch = createEventDispatcher();

  export let data: {
    food_items: MultiFoodItem[];
    guessed_meal: string | null;
    overall_confidence: number;
  };
  export let onClose: () => void;

  let items: MultiFoodItem[] = [];
  let selectedMeal: string = '';
  let isSubmitting = false;
  let error: string | null = null;

  // Subscribe to store
  const unsubscribe = multiFoodFormStore.subscribe(state => {
    items = state.items;
    selectedMeal = state.selectedMeal;
    isSubmitting = state.isSubmitting;
    error = state.error;
  });

  // Map meal to meal_id for API
  const mealIdMap: Record<string, number> = {
    'Breakfast': 1,
    'Lunch': 2,
    'Dinner': 3,
    'Snack': 4,
  };

  onMount(() => {
    multiFoodFormStore.initialize(data.food_items, data.guessed_meal);
    return unsubscribe;
  });

  function handleUpdateItem(event: CustomEvent) {
    const { itemId, updates } = event.detail;
    multiFoodFormStore.updateItem(itemId, updates);
  }

  function handleDeleteItem(event: CustomEvent) {
    const itemId = event.detail;
    multiFoodFormStore.removeItem(itemId);
  }

  function handleMealChange(meal: string) {
    multiFoodFormStore.setMeal(meal);
  }

  function handleAddItems(event: CustomEvent) {
    const newItems = event.detail;
    if (Array.isArray(newItems)) {
      newItems.forEach((item: MultiFoodItem) => {
        multiFoodFormStore.addItem(item);
      });
    }
  }

  // Helper: Get weight in grams (user-specified or 100g default)
  function getWeightGrams(item: MultiFoodItem): number {
    if (item.weight_grams !== null && item.weight_grams > 0) {
      return item.weight_grams;
    }
    // Default to 100g if not specified
    return 100;
  }

  async function handleSubmit() {
    // Validate: at least one item, all items must have a selected food
    const validItems = items.filter(item => item.selected_food_id !== null);
    
    if (validItems.length === 0) {
      multiFoodFormStore.setError('Please select at least one food item');
      return;
    }

    if (validItems.length !== items.length) {
      multiFoodFormStore.setError('Some items have no match. Please edit or remove them.');
      return;
    }

    multiFoodFormStore.setSubmitting(true);
    multiFoodFormStore.setError(null);

    try {
      // Prepare batch entries with summary info
      const entries = validItems.map(item => ({
        food_id: item.selected_food_id!,
        food_name: item.selected_name!,
        quantity: getWeightGrams(item),
        parsed_quantity: item.parsed_quantity,
        parsed_unit: item.parsed_unit,
        meal_id: mealIdMap[selectedMeal] || 1,
        notes: `${item.parsed_quantity} ${item.parsed_unit}`,  // Store original unit for reference
      }));

      const response = await fetch('/logs/batch-summary', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({
          entries,
          logged_at: (() => {
            const now = new Date();
            return `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}T${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`;
          })(),
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to log foods');
      }

      const result = await response.json();
      
      // Emit the formatted summary for the chat interface
      if (result.formatted_summary) {
        dispatch('summary', { message: result.formatted_summary });
      }
      
      // Success! Close the form and reset
      multiFoodFormStore.reset();
      onClose();
      
      // Optionally send a success message to chat
      // This would be handled by the parent component
    } catch (err) {
      multiFoodFormStore.setError(
        err instanceof Error ? err.message : 'Failed to log foods'
      );
    } finally {
      multiFoodFormStore.setSubmitting(false);
    }
  }

  function handleCancel() {
    multiFoodFormStore.reset();
    onClose();
  }

  function handleBackdropClick() {
    if (!isSubmitting) {
      handleCancel();
    }
  }

  $: canSubmit = items.length > 0 && items.every(item => item.selected_food_id !== null) && !isSubmitting;
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
    class="relative bg-white rounded-t-lg md:rounded-lg shadow-xl w-full md:max-w-2xl md:mx-4 max-h-[85vh] flex flex-col"
    on:click|stopPropagation
    on:keydown|stopPropagation
    role="dialog"
    aria-modal="true"
    aria-labelledby="confirm-foods-title"
  >
    <!-- Header -->
    <div class="flex-none bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between rounded-t-lg">
      <h3 id="confirm-foods-title" class="text-lg font-semibold text-gray-900">Confirm Foods</h3>
      <button type="button"
        on:click={handleCancel}
        class="text-gray-400 hover:text-gray-600"
        disabled={isSubmitting}
        style="min-width: 44px; min-height: 44px;"
      >
        <svg class="w-6 h-6 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <!-- Content (scrollable) -->
    <div class="flex-1 overflow-y-auto px-4 py-2">
      <!-- Food Items List -->
      {#if items.length === 0}
        <div class="text-center py-8 text-gray-500">
          <p>No items to log.</p>
          <p class="text-sm mt-2">Add a food item below.</p>
        </div>
      {:else}
        <div class="divide-y divide-gray-100">
          {#each items as item (item.item_id)}
            <FoodRow
              {item}
              on:update={handleUpdateItem}
              on:delete={handleDeleteItem}
            />
          {/each}
        </div>
      {/if}

      <!-- Add Food -->
      <InlineAddFood on:add={handleAddItems} />

      <!-- Meal Selector -->
      <div class="mt-4 pt-4 border-t border-gray-200">
        <MealSelector
          {selectedMeal}
          onChange={handleMealChange}
        />
      </div>

      <!-- Error Message -->
      {#if error}
        <div class="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      {/if}
    </div>

    <!-- Footer -->
    <div class="flex-none bg-white border-t border-gray-200 px-4 py-3 flex gap-2 rounded-b-lg">
      <button type="button"
        on:click={handleCancel}
        disabled={isSubmitting}
        class="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 text-gray-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
        style="min-height: 44px;"
      >
        ❌ Cancel
      </button>
      <button type="button"
        on:click={handleSubmit}
        disabled={!canSubmit}
        class="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 font-medium disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        style="min-height: 44px;"
      >
        {#if isSubmitting}
          <svg class="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span>Logging...</span>
        {:else}
          <span>✔️ Log Foods</span>
        {/if}
      </button>
    </div>
  </div>
</div>
