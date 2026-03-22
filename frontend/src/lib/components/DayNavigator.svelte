<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  export let date: string; // YYYY-MM-DD

  const dispatch = createEventDispatcher<{ change: string }>();

  $: dateObj = new Date(date + 'T12:00:00');
  $: isToday = date === new Date().toISOString().slice(0, 10);

  $: formatted = dateObj.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: dateObj.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined,
  });

  function offsetDate(days: number) {
    const d = new Date(date + 'T12:00:00');
    d.setDate(d.getDate() + days);
    dispatch('change', d.toISOString().slice(0, 10));
  }
</script>

<div class="flex items-center justify-between px-4 py-3 bg-white border-b border-gray-200">
  <button type="button"
    on:click={() => offsetDate(-1)}
    class="p-2 rounded-full hover:bg-gray-100 active:bg-gray-200 text-gray-600"
    aria-label="Previous day"
  >
    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
    </svg>
  </button>

  <div class="text-center">
    <span class="font-semibold text-gray-900">{formatted}</span>
    {#if isToday}
      <span class="ml-2 text-xs font-medium text-primary-600 bg-primary-50 px-2 py-0.5 rounded-full">Today</span>
    {/if}
  </div>

  <button type="button"
    on:click={() => offsetDate(1)}
    disabled={isToday}
    class="p-2 rounded-full hover:bg-gray-100 active:bg-gray-200 text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
    aria-label="Next day"
  >
    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
    </svg>
  </button>
</div>
