<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import type { UserFood } from '../types/profile';
  import { profileFoodsStore } from '../stores/profileFoods';
  import ProfileFoodItem from './ProfileFoodItem.svelte';

  const dispatch = createEventDispatcher<{ openSheet: UserFood; delete: UserFood }>();

  let query = '';
  let results: UserFood[] = [];
  let searching = false;
  let debounceTimer: ReturnType<typeof setTimeout>;

  $: isSearching = query.trim().length > 0;

  function handleInput() {
    clearTimeout(debounceTimer);
    if (!query.trim()) {
      results = [];
      return;
    }
    searching = true;
    debounceTimer = setTimeout(async () => {
      results = await profileFoodsStore.search(query.trim());
      searching = false;
    }, 250);
  }

  export function clearSearch() {
    query = '';
    results = [];
  }
</script>

<div class="relative">
  <!-- Search input -->
  <div class="relative mx-4 mt-4 mb-2">
    <div class="absolute inset-y-0 left-3 flex items-center pointer-events-none">
      <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    </div>
    <input
      type="search"
      bind:value={query}
      on:input={handleInput}
      placeholder="Search your foods..."
      class="w-full pl-9 pr-9 py-2.5 border border-gray-300 rounded-xl bg-gray-50 focus:bg-white focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm"
    />
    {#if query}
      <button type="button"
        on:click={clearSearch}
        class="absolute inset-y-0 right-3 flex items-center text-gray-400 hover:text-gray-600"
        aria-label="Clear search"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    {/if}
  </div>

  <!-- Search results -->
  {#if isSearching}
    {#if searching}
      <div class="px-4 py-4 text-sm text-gray-400 flex items-center gap-2">
        <svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        Searching...
      </div>
    {:else if results.length === 0}
      <div class="px-4 py-4 text-sm text-gray-500">
        No foods found for "<span class="font-medium">{query}</span>"
      </div>
    {:else}
      <div class="border-t border-gray-100">
        {#each results as uf (uf.id)}
          <ProfileFoodItem userFood={uf} on:openSheet={(e) => dispatch('openSheet', e.detail)} on:delete={(e) => dispatch('delete', e.detail)} />
        {/each}
      </div>
    {/if}
  {/if}
</div>
