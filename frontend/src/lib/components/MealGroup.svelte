<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { MealGroup, DailyLogEntry } from '../types/profile';
  import LogEntry from './LogEntry.svelte';

  export let group: MealGroup;

  const dispatch = createEventDispatcher<{ 
    delete: number; 
    edit: DailyLogEntry;
    copy: DailyLogEntry;
    move: DailyLogEntry;
    copyMeal: MealGroup;
  }>();

  const MEAL_EMOJI: Record<string, string> = {
    Breakfast: '🌅',
    Lunch: '☀️',
    Dinner: '🌙',
    Snack: '🍎',
  };

  $: emoji = MEAL_EMOJI[group.meal.name] ?? '🍽️';
  $: totalCals = group.logs.reduce((sum, l) => sum + (l.calories ?? 0), 0);
</script>

<div class="mb-2">
  <!-- Meal header -->
  <div class="flex items-center justify-between px-4 py-2 bg-gray-50 border-b border-gray-200">
    <div class="flex items-center gap-2">
      <span class="text-base">{emoji}</span>
      <span class="text-xs font-semibold text-gray-600 uppercase tracking-wide">
        {group.meal.name}
      </span>
    </div>
    <div class="flex items-center gap-2">
      {#if group.logs.length > 0}
        <button
          type="button"
          on:click={() => dispatch('copyMeal', group)}
          class="text-xs text-gray-400 hover:text-blue-600 hover:bg-blue-50 px-2 py-1 rounded-lg transition-colors flex items-center gap-1"
          aria-label="Copy meal"
        >
          <span>📋</span> Copy
        </button>
      {/if}
      {#if totalCals > 0}
        <span class="text-xs text-gray-500 font-medium">🔥 {Math.round(totalCals)}</span>
      {/if}
    </div>
  </div>

  <!-- Log entries -->
  {#if group.logs.length === 0}
    <div class="px-4 py-3 text-sm text-gray-400 italic bg-white border-b border-gray-100">
      No foods logged
    </div>
  {:else}
    {#each group.logs as entry (entry.id)}
      <LogEntry
        {entry}
        on:delete={(e) => dispatch('delete', e.detail)}
        on:edit={(e) => dispatch('edit', e.detail)}
        on:copy={(e) => dispatch('copy', e.detail)}
        on:move={(e) => dispatch('move', e.detail)}
      />
    {/each}
  {/if}
</div>
