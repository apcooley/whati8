<script lang="ts">
  import { onMount } from 'svelte';
  import type { DailyLogEntry } from '../types/profile';
  import { dailyLogsStore } from '../stores/dailyLogs';
  import { toastStore } from '../stores/toast';
  import { deleteLog, updateLog } from '../api/daily';
  import EditLogSheet from './EditLogSheet.svelte';
  import DayNavigator from './DayNavigator.svelte';
  import MealGroup from './MealGroup.svelte';
  import DailySummaryBar from './DailySummaryBar.svelte';

  onMount(() => {
    dailyLogsStore.load();
  });

  let editEntry: import('../types/profile').DailyLogEntry | null = null;
  let editVisible = false;

  $: state = $dailyLogsStore;

  let pendingDeleteId: number | null = null;

  function requestDelete(logId: number) {
    pendingDeleteId = logId;
  }

  function cancelDelete() {
    pendingDeleteId = null;
  }

  async function confirmDelete() {
    if (pendingDeleteId === null) return;
    const logId = pendingDeleteId;
    pendingDeleteId = null;
    try {
      await deleteLog(logId);
      toastStore.success('Deleted');
      await dailyLogsStore.load();
    } catch (err) {
      toastStore.error(err instanceof Error ? err.message : 'Failed to delete');
    }
  }

  function handleEdit(entry: DailyLogEntry) {
    editEntry = entry;
    editVisible = true;
  }

  async function handleEditSave(e: CustomEvent<{ logId: number; quantity: number; unit: string; meal_id: number | null }>) {
    const { logId, quantity, unit, meal_id } = e.detail;
    try {
      await updateLog(logId, { quantity, unit, meal_id });
      toastStore.success('Log updated');
      editVisible = false;
      editEntry = null;
      dailyLogsStore.invalidate();
    } catch (err) {
      toastStore.error(err instanceof Error ? err.message : 'Failed to update');
    }
  }

  async function handleEditDelete(e: CustomEvent<number>) {
    editVisible = false;
    editEntry = null;
    pendingDeleteId = e.detail;
    await confirmDelete();
  }
</script>

<div class="flex flex-col h-full bg-gray-50">
  <!-- Date navigation (sticky) -->
  <div class="flex-shrink-0">
    <DayNavigator
      date={state.date}
      on:change={(e) => dailyLogsStore.setDate(e.detail)}
    />
  </div>

  <!-- Scrollable meal groups -->
  <div class="flex-1 overflow-y-auto">
    {#if state.loading}
      <div class="flex items-center justify-center py-12 gap-2 text-gray-400 text-sm">
        <svg class="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        Loading logs...
      </div>
    {:else if state.error}
      <div class="m-4 p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
        {state.error}
      </div>
    {:else if state.data}
      {#if state.data.meals.length === 0}
        <div class="flex flex-col items-center justify-center py-16 px-8 text-center">
          <div class="text-5xl mb-4">📋</div>
          <h3 class="font-semibold text-gray-800 mb-2">No foods logged</h3>
          <p class="text-sm text-gray-500">Go to the Log tab to add foods</p>
        </div>
      {:else}
        <div class="pt-2 pb-4">
          {#each state.data.meals as group (group.meal.id)}
            <MealGroup
              {group}
              on:delete={(e) => requestDelete(e.detail)}
              on:edit={(e) => handleEdit(e.detail)}
            />
          {/each}
        </div>
      {/if}
    {/if}
  </div>

  <EditLogSheet
    entry={editEntry}
    visible={editVisible}
    on:save={handleEditSave}
    on:delete={handleEditDelete}
    on:close={() => { editVisible = false; editEntry = null; }}
  />

  {#if pendingDeleteId !== null}
  <div class="fixed inset-0 bg-black bg-opacity-40 z-40 flex items-center justify-center"
    on:click={cancelDelete} on:keydown={(e) => e.key === 'Escape' && cancelDelete()} role="button" tabindex="-1">
    <div class="bg-white rounded-2xl p-5 mx-6 shadow-xl max-w-sm w-full" on:click|stopPropagation on:keydown|stopPropagation role="dialog">
      <p class="text-gray-900 font-semibold text-lg mb-1">Delete this log?</p>
      <p class="text-gray-500 text-sm mb-4">This can't be undone.</p>
      <div class="flex gap-3">
        <button type="button" on:click={cancelDelete}
          class="flex-1 py-2.5 border border-gray-300 rounded-xl font-medium text-gray-700 hover:bg-gray-50">Cancel</button>
        <button type="button" on:click={confirmDelete}
          class="flex-1 py-2.5 bg-red-600 text-white rounded-xl font-semibold hover:bg-red-700">Delete</button>
      </div>
    </div>
  </div>
{/if}

  <!-- Summary bar (sticky at bottom) -->
  {#if state.data}
    <div class="max-h-[60vh] overflow-y-auto">
      <DailySummaryBar nutrients={state.data?.summary?.nutrients ?? []} on:refresh={() => dailyLogsStore.invalidate()} />
    </div>
  {/if}
</div>
