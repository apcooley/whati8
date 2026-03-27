<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import type { FoodPortion } from '../stores/multiFoodForm';
  import NutrientBadges from './NutrientBadges.svelte';

  export let alternatives: Array<{
    food_id: number;
    name: string;
    serving_size: number;
    serving_unit: string;
    calories: number;
    protein: number;
    fat: number;
    fiber: number;
    portions?: FoodPortion[];
  }>;
  export let currentFoodId: number | null;

  const dispatch = createEventDispatcher();
  let dropdownElement: HTMLDivElement;

  function handleSelect(food: typeof alternatives[0]) {
    dispatch('select', food);
  }

  function handleOther() {
    dispatch('other');
  }

  function handleClickOutside(event: MouseEvent) {
    if (dropdownElement && !dropdownElement.contains(event.target as Node)) {
      dispatch('close');
    }
  }

  onMount(() => {
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  });
</script>

<div
  bind:this={dropdownElement}
  class="absolute z-10 mt-1 w-full bg-white border border-gray-300 rounded-lg shadow-lg max-h-64 overflow-y-auto"
>
  {#each alternatives as food}
    <button type="button"
      on:click={() => handleSelect(food)}
      class="w-full text-left px-4 py-3 hover:bg-primary-50 focus:bg-primary-50 focus:outline-none border-b border-gray-100 last:border-b-0"
      class:bg-primary-100={food.food_id === currentFoodId}
      style="min-height: 44px;"
    >
      <div class="font-medium text-gray-900">{food.name}</div>
      <div class="text-sm text-gray-600 mt-1 flex flex-wrap items-center gap-x-1">
        <span>{food.serving_size || 100} {food.serving_unit === 'undetermined' || !food.serving_unit ? 'g' : food.serving_unit}</span>
        <span>·</span>
        <NutrientBadges calories={food.calories} protein={food.protein} carbs={food.carbs} fat={food.fat} />
      </div>
    </button>
  {/each}
  
  <button type="button"
    on:click={handleOther}
    class="w-full text-left px-4 py-3 hover:bg-gray-50 focus:bg-gray-50 focus:outline-none text-primary-600 font-medium border-t border-gray-200"
    style="min-height: 44px;"
  >
    Other...
  </button>
</div>
