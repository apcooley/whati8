<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { DailyLogEntry } from '../types/profile';

  export let entry: DailyLogEntry;

  const dispatch = createEventDispatcher<{ 
    delete: number; 
    edit: DailyLogEntry;
    copy: DailyLogEntry;
    move: DailyLogEntry;
  }>();

  let showMenu = false;

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

  <div class="relative">
    <button
      type="button"
      on:click={() => showMenu = !showMenu}
      class="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full text-gray-300 hover:text-gray-600 hover:bg-gray-100"
      aria-label="More options"
    >
      <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
        <circle cx="12" cy="5" r="2" />
        <circle cx="12" cy="12" r="2" />
        <circle cx="12" cy="19" r="2" />
      </svg>
    </button>

    {#if showMenu}
      <!-- Backdrop -->
      <div 
        class="fixed inset-0 z-10" 
        on:click={() => showMenu = false}
        on:keydown={(e) => e.key === 'Escape' && (showMenu = false)}
        role="button"
        tabindex="-1"
        aria-label="Close menu"
      ></div>

      <!-- Dropdown menu -->
      <div class="absolute right-0 top-full mt-1 bg-white rounded-xl shadow-lg border border-gray-200 py-1 min-w-[140px] z-20">
        <button
          type="button"
          on:click={() => { showMenu = false; dispatch('edit', entry); }}
          class="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
        >
          <span>✏️</span> Edit
        </button>
        <button
          type="button"
          on:click={() => { showMenu = false; dispatch('copy', entry); }}
          class="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
        >
          <span>📋</span> Copy to...
        </button>
        <button
          type="button"
          on:click={() => { showMenu = false; dispatch('move', entry); }}
          class="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
        >
          <span>↗️</span> Move to...
        </button>
        <div class="border-t border-gray-100 my-1"></div>
        <button
          type="button"
          on:click={() => { showMenu = false; dispatch('delete', entry.id); }}
          class="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
        >
          <span>🗑️</span> Delete
        </button>
      </div>
    {/if}
  </div>
</div>
