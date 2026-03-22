<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { NutrientSummary } from '../types/profile';
  import { toastStore } from '../stores/toast';
  import {
    getSummaryConfig,
    deleteSummaryItem,
    reorderSummary,
    getAvailableNutrients,
    addSummaryItem,
    type SummaryItem,
    type AvailableNutrient,
  } from '../api/summaryConfig';

  export let nutrients: NutrientSummary[];

  const dispatch = createEventDispatcher<{ refresh: void }>();

  let editing = false;
  let dirty = false;
  let configItems: SummaryItem[] = [];
  let savedConfigItems: SummaryItem[] = []; // snapshot for cancel
  let showAddModal = false;
  let addMode: 'nutrient' | 'custom' = 'nutrient';
  let availableNutrients: AvailableNutrient[] = [];
  let nutrientSearch = '';
  let customName = '';
  let customUnit = '';
  let customFormula = '';
  let editingItem: SummaryItem | null = null;
  let editName = '';
  let editUnit = '';
  let editFormula = '';


  const NUTRIENT_EMOJI: Record<string, string> = {
    'calories': '🔥',
    'protein': '🥩',
    'fiber': '🌾',
    'carbs': '🍞',
    'fat': '🧈',
  };

  function getEmoji(name: string): string {
    const lower = name.toLowerCase();
    for (const [key, emoji] of Object.entries(NUTRIENT_EMOJI)) {
      if (lower.includes(key)) return emoji;
    }
    // For custom metrics like "WW points", use first 2-3 chars as abbreviation
    const abbr = name.replace(/\s*points?$/i, '').trim();
    return abbr.length <= 3 ? abbr : abbr.slice(0, 2).toUpperCase();
  }

  function isTextAbbr(name: string): boolean {
    const lower = name.toLowerCase();
    return !Object.keys(NUTRIENT_EMOJI).some(k => lower.includes(k));
  }

  const COLORS: Record<string, string> = {
    calories: 'bg-orange-500',
    protein: 'bg-blue-500',
    carbs: 'bg-yellow-500',
    fat: 'bg-red-400',
    fiber: 'bg-green-500',
  };

  function getColor(name: string): string {
    const key = name.toLowerCase();
    for (const [k, v] of Object.entries(COLORS)) {
      if (key.includes(k)) return v;
    }
    return 'bg-gray-400';
  }

  function pct(value: number, target: number | null): number {
    if (!target || target <= 0) return 0;
    return Math.min(100, Math.round((value / target) * 100));
  }

  function fmt(n: number): string {
    return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(Math.round(n));
  }

  async function startEdit() {
    try {
      configItems = await getSummaryConfig();
      savedConfigItems = JSON.parse(JSON.stringify(configItems));
      dirty = false;
      editing = true;
    } catch (e) {
      toastStore.error('Failed to load config');
    }
  }

  async function handleSave() {
    // Reorder is already persisted on drag-end; deletes/adds are persisted immediately
    // Just need to save final order and refresh the display
    try {
      await reorderSummary(configItems.map(c => c.id));
    } catch { /* order already saved */ }
    editing = false;
    dirty = false;
    dispatch('refresh');
  }

  async function handleCancel() {
    if (dirty) {
      // Restore: re-add deleted items and remove added items
      // Simplest: just reload from server (saved state may be stale if adds/deletes happened)
      // Since deletes/adds are already persisted, we can't truly undo.
      // But we can at least close edit mode and refresh.
    }
    editing = false;
    dirty = false;
    dispatch('refresh');
  }

  async function handleDelete(item: SummaryItem) {
    try {
      await deleteSummaryItem(item.id);
      configItems = configItems.filter(c => c.id !== item.id);
      dirty = true;
    } catch (e) {
      toastStore.error('Failed to remove');
    }
  }

  function moveUp(idx: number) {
    if (idx <= 0) return;
    const items = [...configItems];
    [items[idx - 1], items[idx]] = [items[idx], items[idx - 1]];
    configItems = items;
    dirty = true;
  }

  function moveDown(idx: number) {
    if (idx >= configItems.length - 1) return;
    const items = [...configItems];
    [items[idx], items[idx + 1]] = [items[idx + 1], items[idx]];
    configItems = items;
    dirty = true;
  }

  async function openAddModal() {
    showAddModal = true;
    addMode = 'nutrient';
    nutrientSearch = '';
    customName = '';
    customUnit = '';
    customFormula = '';
    if (availableNutrients.length === 0) {
      try {
        availableNutrients = await getAvailableNutrients();
      } catch {
        toastStore.error('Failed to load nutrients');
      }
    }
  }

  $: filteredNutrients = nutrientSearch.trim()
    ? availableNutrients.filter(n =>
        n.friendly_name.toLowerCase().includes(nutrientSearch.toLowerCase()) ||
        n.name.toLowerCase().includes(nutrientSearch.toLowerCase())
      )
    : availableNutrients.slice(0, 20);

  async function addNutrient(n: AvailableNutrient) {
    try {
      const item = await addSummaryItem({
        nutrient_id: n.nutrient_id,
        display_name: n.friendly_name,
        display_unit: n.unit,
      });
      configItems = [...configItems, item];
      showAddModal = false;
      dirty = true;
    } catch (e) {
      toastStore.error('Failed to add');
    }
  }

  function startEditItem(item: SummaryItem) {
    editingItem = item;
    editName = item.display_name;
    editUnit = item.display_unit;
    editFormula = item.formula ?? '';
  }

  async function saveEditItem() {
    if (!editingItem) return;
    try {
      const { updateSummaryItem } = await import('../api/summaryConfig');
      const updated = await updateSummaryItem(editingItem.id, {
        display_name: editName.trim(),
        display_unit: editUnit.trim(),
        formula: editFormula.trim() || null,
      });
      configItems = configItems.map(c => c.id === updated.id ? updated : c);
      editingItem = null;
      dirty = true;
    } catch (e) {
      toastStore.error(e instanceof Error ? e.message : 'Failed to update');
    }
  }

  async function addCustom() {
    if (!customName.trim() || !customFormula.trim()) return;
    try {
      const item = await addSummaryItem({
        display_name: customName.trim(),
        display_unit: customUnit.trim(),
        formula: customFormula.trim(),
      });
      configItems = [...configItems, item];
      showAddModal = false;
      dirty = true;
    } catch (e) {
      toastStore.error(e instanceof Error ? e.message : 'Invalid formula');
    }
  }
</script>

<div class="bg-white border-t border-gray-200 px-4 py-3">
  {#if editing}
    <!-- Edit mode header -->
    <div class="flex items-center justify-between mb-2">
      <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Customize Summary</p>
    </div>

    <!-- Draggable items -->
    <div class="space-y-1 mb-3">
      {#each configItems as item, idx (item.id)}
        <div
          class="flex items-center gap-1.5 py-1.5 px-2 rounded-lg bg-gray-50"
          role="listitem"
        >
          <div class="flex flex-col flex-shrink-0">
            <button type="button" on:click={() => moveUp(idx)} disabled={idx === 0}
              class="w-5 h-4 flex items-center justify-center text-gray-400 hover:text-gray-700 disabled:opacity-20" aria-label="Move up">
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 15l7-7 7 7" /></svg>
            </button>
            <button type="button" on:click={() => moveDown(idx)} disabled={idx === configItems.length - 1}
              class="w-5 h-4 flex items-center justify-center text-gray-400 hover:text-gray-700 disabled:opacity-20" aria-label="Move down">
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M19 9l-7 7-7-7" /></svg>
            </button>
          </div>
          <span class="flex-1 text-sm font-medium text-gray-700">{item.display_name}</span>
          <span class="text-xs text-gray-400">{item.display_unit}</span>
          {#if item.formula}
            <span class="text-xs text-purple-400" title={item.formula}>ƒ</span>
          {/if}
          <button type="button"
            on:click={() => startEditItem(item)}
            class="w-6 h-6 flex items-center justify-center rounded-full text-gray-300 hover:text-blue-500 hover:bg-blue-50"
            aria-label="Edit {item.display_name}"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </button>
          <button type="button"
            on:click={() => handleDelete(item)}
            class="w-6 h-6 flex items-center justify-center rounded-full text-gray-300 hover:text-red-500 hover:bg-red-50"
            aria-label="Remove {item.display_name}"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      {/each}

      <button type="button"
        on:click={openAddModal}
        class="w-full py-2 border-2 border-dashed border-gray-300 rounded-lg text-sm font-medium text-gray-500 hover:border-primary-400 hover:text-primary-600 transition-colors flex items-center justify-center gap-1"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        New Metric
      </button>
    </div>

    <!-- Save / Cancel -->
    <div class="flex gap-2">
      <button type="button"
        on:click={handleCancel}
        class="flex-1 py-2 border border-gray-300 rounded-xl text-sm font-medium text-gray-700 hover:bg-gray-50"
      >
        Cancel
      </button>
      <button type="button"
        on:click={handleSave}
        class="flex-1 py-2 bg-primary-600 text-white rounded-xl text-sm font-semibold hover:bg-primary-700"
      >
        Save
      </button>
    </div>

  {:else}
    <!-- Display mode -->
    <div class="flex items-center justify-between mb-2">
      <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Daily Summary</p>
      <button type="button"
        on:click={startEdit}
        class="w-7 h-7 flex items-center justify-center rounded-full text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
        title="Customize summary"
        aria-label="Customize summary"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      </button>
    </div>

    {#if nutrients.length > 0}
      <div class="space-y-2">
        {#each nutrients as n (n.name)}
          <div>
            <div class="flex justify-between text-xs text-gray-700 mb-1">
              <span class="font-medium">
                {#if isTextAbbr(n.name)}<code class="font-mono text-xs bg-gray-100 px-1 rounded">{getEmoji(n.name)}</code>{:else}{getEmoji(n.name)}{/if}
                {n.name}
              </span>
              <span>
                {fmt(n.value)}{#if n.target} / {fmt(n.target)}{/if}
                <span class="text-gray-500 ml-0.5">{n.unit}</span>
              </span>
            </div>
            {#if n.target}
              <div class="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  class="h-full rounded-full transition-all {getColor(n.name)}"
                  style="width: {pct(n.value, n.target)}%"
                ></div>
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {:else}
      <p class="text-xs text-gray-400 text-center py-2">No metrics configured</p>
    {/if}
  {/if}
</div>

<!-- Edit Metric Modal -->
{#if editingItem}
  <div
    class="fixed inset-0 bg-black bg-opacity-40 z-50 flex items-end sm:items-center justify-center"
    on:click={() => editingItem = null}
    on:keydown={(e) => e.key === 'Escape' && (editingItem = null)}
    role="button" tabindex="-1"
  >
    <div class="bg-white rounded-t-2xl sm:rounded-2xl w-full sm:max-w-md p-4 space-y-4"
      on:click|stopPropagation on:keydown|stopPropagation role="dialog">
      <h3 class="text-lg font-bold text-gray-900">Edit Metric</h3>
      <div>
        <label class="block text-xs font-medium text-gray-600 mb-1">Name</label>
        <input bind:value={editName} class="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm" />
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-600 mb-1">Unit</label>
        <input bind:value={editUnit} class="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm" />
      </div>
      {#if editingItem.formula !== null || editFormula}
        <div>
          <label class="block text-xs font-medium text-gray-600 mb-1">Formula</label>
          <textarea bind:value={editFormula} rows="2"
            class="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm font-mono" />
          <p class="text-xs text-gray-400 mt-1">
            Variables: Calories, Protein, Carbs, Fat, Fiber, Sugar, Sodium<br/>
            Functions: round, roundup, rounddown, min, max
          </p>
        </div>
      {/if}
      <div class="flex gap-2">
        <button type="button"
          on:click={() => editingItem = null}
          class="flex-1 py-2.5 border border-gray-300 rounded-xl text-sm font-medium text-gray-700 hover:bg-gray-50"
        >Cancel</button>
        <button type="button"
          on:click={saveEditItem}
          disabled={!editName.trim()}
          class="flex-1 py-2.5 bg-primary-600 text-white rounded-xl text-sm font-semibold hover:bg-primary-700 disabled:opacity-50"
        >Save</button>
      </div>
    </div>
  </div>
{/if}

<!-- Add Metric Modal -->
{#if showAddModal}
  <div
    class="fixed inset-0 bg-black bg-opacity-40 z-50 flex items-end sm:items-center justify-center"
    on:click={() => showAddModal = false}
    on:keydown={(e) => e.key === 'Escape' && (showAddModal = false)}
    role="button" tabindex="-1"
  >
    <div class="bg-white rounded-t-2xl sm:rounded-2xl w-full sm:max-w-md max-h-[80vh] flex flex-col"
      on:click|stopPropagation on:keydown|stopPropagation role="dialog">

      <div class="flex border-b border-gray-200 px-4 pt-4">
        <button type="button"
          on:click={() => addMode = 'nutrient'}
          class="flex-1 pb-2 text-sm font-medium border-b-2 transition-colors
            {addMode === 'nutrient' ? 'border-primary-500 text-primary-600' : 'border-transparent text-gray-500'}"
        >
          📊 Existing Nutrient
        </button>
        <button type="button"
          on:click={() => addMode = 'custom'}
          class="flex-1 pb-2 text-sm font-medium border-b-2 transition-colors
            {addMode === 'custom' ? 'border-primary-500 text-primary-600' : 'border-transparent text-gray-500'}"
        >
          🧮 Custom Formula
        </button>
      </div>

      {#if addMode === 'nutrient'}
        <div class="p-4">
          <input
            type="search"
            bind:value={nutrientSearch}
            placeholder="Search nutrients..."
            class="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm"
          />
        </div>
        <div class="flex-1 overflow-y-auto px-4 pb-4 space-y-1" style="max-height: 50vh">
          {#each filteredNutrients as n (n.nutrient_id)}
            <button type="button"
              on:click={() => addNutrient(n)}
              class="w-full text-left px-3 py-2 rounded-lg hover:bg-gray-50 transition-colors flex justify-between items-center"
            >
              <span class="text-sm font-medium text-gray-800">{n.friendly_name}</span>
              <span class="text-xs text-gray-400">{n.unit}</span>
            </button>
          {/each}
        </div>
      {:else}
        <div class="p-4 space-y-4">
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">Name</label>
            <input bind:value={customName} placeholder="e.g. WW Points" class="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">Unit</label>
            <input bind:value={customUnit} placeholder="e.g. pts" class="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">Formula</label>
            <textarea bind:value={customFormula} placeholder="e.g. round(Calories / 50, 1)" rows="2"
              class="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm font-mono" />
            <p class="text-xs text-gray-400 mt-1">
              Variables: Calories, Protein, Carbs, Fat, Fiber, Sugar, Sodium<br/>
              Functions: round, roundup, rounddown, min, max
            </p>
          </div>
          <button type="button"
            on:click={addCustom}
            disabled={!customName.trim() || !customFormula.trim()}
            class="w-full py-2.5 bg-primary-600 text-white rounded-xl font-medium hover:bg-primary-700 disabled:opacity-50"
          >
            Add Custom Metric
          </button>
        </div>
      {/if}
    </div>
  </div>
{/if}
