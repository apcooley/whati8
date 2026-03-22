<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { DailyLogEntry } from '../types/profile';

  export let entry: DailyLogEntry;

  const dispatch = createEventDispatcher<{ delete: number; edit: DailyLogEntry }>();

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
</script>

<div class="flex items-center gap-3 px-4 py-3 bg-white border-b border-gray-100">
  <div
    class="flex-1 min-w-0 cursor-pointer active:bg-gray-50 -m-1 p-1 rounded-lg"
    role="button"
    tabindex="0"
    on:click={() => dispatch('edit', entry)}
    on:keydown={(e) => e.key === 'Enter' && dispatch('edit', entry)}
  >
    <p class="font-medium text-gray-900 truncate text-sm">{entry.food_name}</p>
    <div class="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 mt-0.5">
      <span class="text-xs text-gray-400">{entry.quantity} {entry.unit}</span>
      {#if entry.summary_nutrients}
        {#each entry.summary_nutrients as sn}
          {#if sn.value !== 0}
            <span class="text-xs" title="{sn.name}">
              {#if isText(sn.name)}<code class="font-mono text-[10px] bg-gray-100 px-0.5 rounded">{getEmoji(sn.name)}</code>{:else}{getEmoji(sn.name)}{/if}<span class="font-medium text-gray-700">{sn.value}</span>
            </span>
          {/if}
        {/each}
      {:else if entry.calories != null}
        <span class="text-xs">🔥<span class="text-orange-600 font-medium">{Math.round(entry.calories)}</span></span>
      {/if}
    </div>
  </div>

  <button
    type="button"
    on:click={() => dispatch('edit', entry)}
    class="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full text-gray-300 hover:text-blue-500 hover:bg-blue-50"
    aria-label="Edit log"
  >
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
    </svg>
  </button>

  <button
    type="button"
    on:click={() => dispatch('delete', entry.id)}
    class="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full text-gray-300 hover:text-red-500 hover:bg-red-50"
    aria-label="Delete log"
  >
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
    </svg>
  </button>
</div>
