<script lang="ts">
  export let selectedMeal: string;
  export let onChange: (meal: string) => void;

  const meals = ['Breakfast', 'Lunch', 'Dinner', 'Snack'];
</script>

<div class="mb-4">
  <label for="meal-selector" class="block text-sm font-medium text-gray-700 mb-2">Meal</label>
  <select
    id="meal-selector"
    bind:value={selectedMeal}
    on:change={() => onChange(selectedMeal)}
    class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-base"
    style="min-height: 44px;"
  >
    {#each meals as meal}
      <option value={meal}>{meal}</option>
    {/each}
  </select>
</div>
