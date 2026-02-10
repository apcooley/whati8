<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { MultiFoodItem } from '../stores/multiFoodForm';
  import FoodSelector from './FoodSelector.svelte';
  import QuantityEditor from './QuantityEditor.svelte';
  import AddFoodModal from './AddFoodModal.svelte';

  export let item: MultiFoodItem;

  const dispatch = createEventDispatcher();

  let isEditMode = false;
  let editText = item.raw_text;
  let showFoodSelector = false;
  let showQuantityEditor = false;
  let isSearching = false;
  let showAddFoodModal = false;

  function handleFoodClick() {
    if (item.alternatives && item.alternatives.length > 0) {
      showFoodSelector = !showFoodSelector;
    }
  }

  function handleQuantityClick() {
    showQuantityEditor = true;
  }

  function handleEdit() {
    isEditMode = true;
    editText = item.raw_text;
  }

  function handleDelete() {
    dispatch('delete', item.item_id);
  }

  async function handleSearch() {
    if (!editText.trim()) return;

    isSearching = true;

    try {
      const response = await fetch(`/foods/search?q=${encodeURIComponent(editText)}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
      });

      if (!response.ok) {
        throw new Error('Search failed');
      }

      const data = await response.json();
      const foods = data.results || [];
      
      // Update item with new alternatives (including portions)
      dispatch('update', {
        itemId: item.item_id,
        updates: {
          raw_text: editText,
          alternatives: foods.map((f: any) => ({
            food_id: f.id,
            name: f.name,
            serving_size: f.serving_size,
            serving_unit: f.unit,
            calories: f.calories,
            protein: f.protein,
            fat: f.fat,
            fiber: f.fiber,
            portions: f.portions || [],
          })),
          // Also update selected food if we have results
          ...(foods.length > 0 ? {
            selected_food_id: foods[0].id,
            selected_name: foods[0].name,
            serving_size: foods[0].serving_size,
            serving_unit: foods[0].unit,
            calories: foods[0].calories,
            protein: foods[0].protein,
            fat: foods[0].fat,
            fiber: foods[0].fiber,
            portions: foods[0].portions || [],
          } : {}),
          status: foods.length > 0 ? 'matched' : 'not_found',
        },
      });
      
      isEditMode = false;
    } catch (err) {
      console.error('Search error:', err);
    } finally {
      isSearching = false;
    }
  }

  function handleAddAsIs() {
    showAddFoodModal = true;
  }

  function handleFoodCreated(event: CustomEvent) {
    const newFood = event.detail;
    showAddFoodModal = false;
    
    // Update item with the created food
    // Set quantity to the serving size so nutrition displays correctly
    dispatch('update', {
      itemId: item.item_id,
      updates: {
        selected_food_id: newFood.id,
        selected_name: newFood.name,
        serving_size: newFood.serving_size,
        serving_unit: newFood.unit,
        parsed_quantity: newFood.serving_size,  // Set quantity to serving size
        parsed_unit: newFood.unit,              // Set unit to match
        calories: newFood.food_nutrients?.find((fn: any) => fn.nutrient.name === 'Energy' || fn.nutrient.name === 'Energy (kcal)')?.amount_per_serving || 0,
        protein: newFood.food_nutrients?.find((fn: any) => fn.nutrient.name === 'Protein')?.amount_per_serving || 0,
        fat: newFood.food_nutrients?.find((fn: any) => fn.nutrient.name === 'Total lipid (fat)')?.amount_per_serving || 0,
        fiber: newFood.food_nutrients?.find((fn: any) => fn.nutrient.name === 'Fiber, total dietary')?.amount_per_serving || null,
        status: 'matched',
      },
    });
    
    isEditMode = false;
  }

  function handleAddFoodCancel() {
    showAddFoodModal = false;
  }

  function handleFoodSelect(event: CustomEvent) {
    const food = event.detail;
    dispatch('update', {
      itemId: item.item_id,
      updates: {
        selected_food_id: food.food_id,
        selected_name: food.name,
        serving_size: food.serving_size,
        serving_unit: food.serving_unit,
        calories: food.calories,
        protein: food.protein,
        fat: food.fat,
        fiber: food.fiber,
        portions: food.portions || [],
        status: 'matched',
      },
    });
    showFoodSelector = false;
  }

  function handleQuantitySave(event: CustomEvent) {
    dispatch('update', {
      itemId: item.item_id,
      updates: event.detail,
    });
    showQuantityEditor = false;
  }
</script>

<div class="border-b border-gray-100 py-3 px-2 relative">
  {#if isEditMode}
    <!-- Edit Mode -->
    <div class="flex items-center gap-2">
      <input
        type="text"
        bind:value={editText}
        class="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
        style="min-height: 44px;"
        placeholder="e.g., 2 eggs"
        on:keydown={(e) => {
          if (e.key === 'Enter') {
            handleSearch();
          } else if (e.key === 'Escape') {
            isEditMode = false;
          }
        }}
      />
      <button
        on:click={handleAddAsIs}
        class="px-3 py-2 text-primary-600 hover:bg-primary-50 rounded-lg font-medium"
        style="min-height: 44px; min-width: 44px;"
        title="Add as-is"
      >
        ➕
      </button>
      <button
        on:click={handleSearch}
        disabled={isSearching}
        class="px-3 py-2 text-primary-600 hover:bg-primary-50 rounded-lg font-medium disabled:text-gray-400"
        style="min-height: 44px; min-width: 44px;"
        title="Search"
      >
        {#if isSearching}
          <svg class="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        {:else}
          🔎
        {/if}
      </button>
      <button
        on:click={() => { isEditMode = false; editText = item.raw_text; }}
        class="px-3 py-2 text-gray-600 hover:bg-gray-50 border border-gray-300 rounded-lg font-medium"
        style="min-height: 44px;"
        title="Cancel"
      >
        Cancel
      </button>
    </div>
  {:else}
    <!-- Display Mode -->
    <div class="flex items-center gap-2">
      <button
        on:click={handleFoodClick}
        class="flex-1 text-left px-3 py-2 rounded-lg hover:bg-gray-50 focus:bg-gray-50 focus:outline-none"
        class:text-red-600={item.status === 'not_found'}
        class:font-semibold={item.status === 'not_found'}
        style="min-height: 44px;"
      >
        <span class="font-medium">
          {item.selected_name || item.raw_text}
          {#if item.status === 'not_found'}
            <span class="text-sm">(no match)</span>
          {/if}
        </span>
      </button>
      
      <button
        on:click={handleQuantityClick}
        class="px-3 py-2 text-gray-700 hover:bg-gray-50 rounded-lg font-medium whitespace-nowrap"
        style="min-height: 44px;"
        disabled={!item.selected_food_id}
      >
        {item.parsed_quantity} {item.parsed_unit}
      </button>
      
      <button
        on:click={handleEdit}
        class="px-2 py-2 text-gray-600 hover:bg-gray-50 rounded-lg"
        style="min-height: 44px; min-width: 44px;"
        title="Edit"
      >
        ✏️
      </button>
      
      <button
        on:click={handleDelete}
        class="px-2 py-2 text-red-600 hover:bg-red-50 rounded-lg"
        style="min-height: 44px; min-width: 44px;"
        title="Delete"
      >
        🗑️
      </button>
    </div>
  {/if}

  <!-- Food Selector Dropdown -->
  {#if showFoodSelector && item.alternatives}
    <FoodSelector
      alternatives={item.alternatives}
      currentFoodId={item.selected_food_id}
      on:select={handleFoodSelect}
      on:close={() => showFoodSelector = false}
      on:other={() => {
        showFoodSelector = false;
        handleEdit();
      }}
    />
  {/if}
</div>

<!-- Quantity Editor Modal -->
{#if showQuantityEditor}
  <QuantityEditor
    {item}
    on:save={handleQuantitySave}
    on:cancel={() => showQuantityEditor = false}
  />
{/if}

<!-- Add Food Modal -->
{#if showAddFoodModal}
  <AddFoodModal 
    initialName={editText}
    on:created={handleFoodCreated}
    on:cancel={handleAddFoodCancel}
  />
{/if}
