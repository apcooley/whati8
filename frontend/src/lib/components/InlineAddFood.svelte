<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import AddFoodModal from './AddFoodModal.svelte';

  const dispatch = createEventDispatcher();

  let isExpanded = false;
  let inputText = '';
  let isLoading = false;
  let error: string | null = null;
  let showAddFoodModal = false;
  let searchTerm = '';

  async function handleSubmit() {
    if (!inputText.trim()) return;

    isLoading = true;
    error = null;

    try {
      const response = await fetch('/foods/resolve', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({ text: inputText }),
      });

      if (!response.ok) {
        throw new Error('Failed to resolve food');
      }

      const data = await response.json();
      
      // Transform resolved_items to MultiFoodItem format
      const transformedItems = (data.resolved_items || []).map((item: any) => {
        const topMatch = item.matches?.[0] || null;
        return {
          item_id: typeof crypto !== 'undefined' && crypto.randomUUID 
            ? crypto.randomUUID() 
            : 'id-' + Math.random().toString(36).substr(2, 9) + '-' + Date.now().toString(36),
          raw_text: item.parsed_item.original_text,
          parsed_quantity: item.parsed_item.quantity,
          parsed_unit: item.parsed_item.unit,
          confidence: item.parsed_item.confidence,
          selected_food_id: topMatch?.food_id || null,
          selected_name: topMatch?.name || null,
          serving_size: topMatch?.serving_size || null,
          serving_unit: topMatch?.unit || null,
          calories: topMatch?.calories || null,
          protein: topMatch?.protein || null,
          fat: topMatch?.fat || null,
          fiber: topMatch?.fiber || null,
          alternatives: (item.matches || []).map((m: any) => ({
            food_id: m.food_id,
            name: m.name,
            serving_size: m.serving_size,
            unit: m.unit,
            calories: m.calories,
            protein: m.protein,
            fat: m.fat || null,
            similarity_score: m.similarity_score,
          })),
          status: item.status || 'matched',
        };
      });
      
      if (transformedItems.length === 0) {
        throw new Error('No foods found');
      }
      
      // Emit the resolved items
      dispatch('add', transformedItems);
      
      // Reset
      inputText = '';
      isExpanded = false;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to add food';
    } finally {
      isLoading = false;
    }
  }

  function handleExpand() {
    isExpanded = true;
  }

  function handleCancel() {
    isExpanded = false;
    inputText = '';
    error = null;
  }

  function handleOpenAddFood() {
    searchTerm = inputText;
    showAddFoodModal = true;
  }

  function handleFoodCreated(event: any) {
    const newFood = event.detail;
    showAddFoodModal = false;
    
    // Convert created food to MultiFoodItem format
    // Set quantity to serving size so nutrition displays correctly
    // Include portions for QuantityEditor to calculate nutrition properly
    const foodItem = {
      item_id: typeof crypto !== 'undefined' && crypto.randomUUID 
        ? crypto.randomUUID() 
        : 'id-' + Math.random().toString(36).substr(2, 9) + '-' + Date.now().toString(36),
      raw_text: newFood.name,
      parsed_quantity: newFood.serving_size,  // Use serving size, not 1
      parsed_unit: newFood.unit,
      confidence: 1.0,
      selected_food_id: newFood.id,
      selected_name: newFood.name,
      serving_size: newFood.serving_size,
      serving_unit: newFood.unit,
      calories: newFood.food_nutrients?.find((fn: any) => fn.nutrient.name === 'Energy' || fn.nutrient.name === 'Energy (kcal)')?.amount_per_serving || 0,
      protein: newFood.food_nutrients?.find((fn: any) => fn.nutrient.name === 'Protein')?.amount_per_serving || 0,
      fat: newFood.food_nutrients?.find((fn: any) => fn.nutrient.name === 'Total lipid (fat)')?.amount_per_serving || 0,
      fiber: newFood.food_nutrients?.find((fn: any) => fn.nutrient.name === 'Fiber, total dietary')?.amount_per_serving || null,
      portions: newFood.portions || [],       // Include portions for calculation
      alternatives: [],
      status: 'matched',
    };
    
    // Emit to parent
    dispatch('add', [foodItem]);
    
    // Reset
    inputText = '';
    isExpanded = false;
  }

  function handleAddFoodCancel() {
    showAddFoodModal = false;
  }
</script>

<div class="border-t border-gray-200 pt-3 pb-3">
  {#if !isExpanded}
    <button
      on:click={handleExpand}
      class="w-full px-4 py-3 border-2 border-dashed border-gray-300 rounded-lg hover:border-primary-400 hover:bg-primary-50 text-gray-600 hover:text-primary-600 font-medium transition-colors"
      style="min-height: 44px;"
    >
      <span class="text-xl mr-2">+</span> Add another food...
    </button>
  {:else}
    <div class="space-y-2">
      <div class="flex gap-2">
        <input
          type="text"
          bind:value={inputText}
          placeholder="e.g., 1 banana"
          class="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          style="min-height: 44px;"
          disabled={isLoading}
          on:keydown={(e) => {
            if (e.key === 'Enter') {
              handleSubmit();
            } else if (e.key === 'Escape') {
              handleCancel();
            }
          }}
        />
        <button
          on:click={handleSubmit}
          disabled={isLoading || !inputText.trim()}
          class="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-300 disabled:cursor-not-allowed font-medium"
          style="min-height: 44px;"
        >
          {#if isLoading}
            <svg class="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          {:else}
            Add
          {/if}
        </button>
        <button
          on:click={handleCancel}
          class="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 text-gray-700"
          style="min-height: 44px;"
          disabled={isLoading}
        >
          Cancel
        </button>
      </div>
      {#if error}
        <div class="text-sm text-red-600 px-2 flex items-center justify-between">
          <span>{error}</span>
          <button
            on:click={handleOpenAddFood}
            class="ml-2 text-xs font-medium text-primary-600 hover:text-primary-700 underline whitespace-nowrap"
          >
            Create custom food instead
          </button>
        </div>
      {/if}
    </div>
  {/if}
</div>

{#if showAddFoodModal}
  <AddFoodModal 
    initialName={searchTerm}
    on:created={handleFoodCreated}
    on:cancel={handleAddFoodCancel}
  />
{/if}
