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

  const NUTRIENT_EMOJI: Record<string, string> = {
    'calories': '🔥', 'protein': '🥩', 'fiber': '🌾', 'carbs': '🍞', 'fat': '🧈',
  };

  function getEmoji(name: string): string {
    const lower = name.toLowerCase();
    for (const [key, emoji] of Object.entries(NUTRIENT_EMOJI)) {
      if (lower.includes(key)) return emoji;
    }
    return name.replace(/\s*points?$/i, '').trim().slice(0, 2).toUpperCase();
  }

  function isText(name: string): boolean {
    return !Object.keys(NUTRIENT_EMOJI).some(k => name.toLowerCase().includes(k));
  }

  $: emoji = MEAL_EMOJI[group.meal.name] ?? '🍽️';

  // Aggregate summary_nutrients across all logs in this meal
  $: mealTotals = (() => {
    const totals: Record<string, { name: string; value: number }> = {};
    for (const log of group.logs) {
      for (const sn of (log.summary_nutrients ?? [])) {
        if (!totals[sn.name]) totals[sn.name] = { name: sn.name, value: 0 };
        totals[sn.name].value += sn.value;
      }
    }
    return Object.values(totals).filter(t => t.value !== 0);
  })();
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
      {#if mealTotals.length > 0}
        <span class="flex items-center gap-1.5 text-xs text-gray-500">
          {#each mealTotals as t}
            <span title={t.name}>
              {#if isText(t.name)}<code class="font-mono text-[10px] bg-gray-100 px-0.5 rounded">{getEmoji(t.name)}</code>{:else}{getEmoji(t.name)}{/if}<span class="font-medium">{Math.round(t.value)}</span>
            </span>
          {/each}
        </span>
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
