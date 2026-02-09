<script lang="ts">
  export let data: {
    calories?: number;
    protein?: number;
    carbs?: number;
    fat?: number;
  };
</script>

<div class="bg-white border border-gray-200 rounded-lg p-4 mt-2">
  <h4 class="font-semibold text-gray-900 mb-2">Nutrition</h4>
  <div class="grid grid-cols-2 gap-2 text-sm">
    {#if data.calories !== undefined}
      <div>
        <span class="text-gray-600">Calories:</span>
        <span class="font-medium">{data.calories}</span>
      </div>
    {/if}
    {#if data.protein !== undefined}
      <div>
        <span class="text-gray-600">Protein:</span>
        <span class="font-medium">{data.protein}g</span>
      </div>
    {/if}
    {#if data.carbs !== undefined}
      <div>
        <span class="text-gray-600">Carbs:</span>
        <span class="font-medium">{data.carbs}g</span>
      </div>
    {/if}
    {#if data.fat !== undefined}
      <div>
        <span class="text-gray-600">Fat:</span>
        <span class="font-medium">{data.fat}g</span>
      </div>
    {/if}
  </div>
</div>
