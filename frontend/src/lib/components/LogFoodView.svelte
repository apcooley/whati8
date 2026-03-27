<script lang="ts">
  import { onMount } from 'svelte';
  import type { UserFood } from '../types/profile';
  import { getDisplayName, getServingLabel } from '../types/profile';
  import { profileFoodsStore } from '../stores/profileFoods';
  import { dailyLogsStore } from '../stores/dailyLogs';
  import { toastStore } from '../stores/toast';
  import { navStore } from '../stores/nav';
  import { quickLog } from '../api/daily';
  import { deleteUserFood } from '../api/profile';
  import ProfileFoodSearch from './ProfileFoodSearch.svelte';
  import ProfileFoodItem from './ProfileFoodItem.svelte';
  import QuickLogSheet from './QuickLogSheet.svelte';
  import EditFoodSheet from './EditFoodSheet.svelte';

  let sheetFood: UserFood | null = null;
  let editFood: UserFood | null = null;
  let editVisible = false;
  let searchRef: ProfileFoodSearch;
  let sheetVisible = false;
  let loggingId: number | null = null;

  onMount(() => {
    profileFoodsStore.load();
  });

  function openSheet(uf: UserFood) {
    sheetFood = uf;
    sheetVisible = true;
  }

  function closeSheet() {
    sheetVisible = false;
    sheetFood = null;
  }

  async function handleLog(e: CustomEvent<{ quantity: number; unit: string; meal_id: number | null }>) {
    if (!sheetFood) return;
    const userFoodId = sheetFood.id;
    const name = getDisplayName(sheetFood);
    loggingId = userFoodId;
    closeSheet();
    const { quantity, unit, meal_id } = e.detail;
    try {
      await quickLog({ user_food_id: userFoodId, quantity, unit, meal_id });
      toastStore.success(`Logged ${name} (${quantity} ${unit})`);
      profileFoodsStore.invalidate();
      dailyLogsStore.invalidate();
      searchRef?.clearSearch();
    } catch (err) {
      toastStore.error(err instanceof Error ? err.message : 'Failed to log food');
    } finally {
      loggingId = null;
    }
  }

  async function handleDelete(e: CustomEvent<UserFood>) {
    const uf = e.detail;
    const name = getDisplayName(uf);
    try {
      await deleteUserFood(uf.id);
      toastStore.success(`Removed "${name}" from your foods`);
      profileFoodsStore.invalidate();
    } catch (err) {
      toastStore.error(err instanceof Error ? err.message : 'Failed to remove food');
    }
  }

  $: favorites = $profileFoodsStore.favorites;
  $: recent = $profileFoodsStore.recent;
  $: loading = $profileFoodsStore.loading;
</script>

<div class="flex flex-col h-full overflow-hidden">
  <!-- Search section (sticky) -->
  <div class="flex-shrink-0 bg-white border-b border-gray-200">
    <ProfileFoodSearch bind:this={searchRef} on:openSheet={(e) => openSheet(e.detail)} on:delete={handleDelete} />
  </div>

  <!-- Scrollable content -->
  <div class="flex-1 overflow-y-auto bg-gray-50">
    {#if loading && favorites.length === 0 && recent.length === 0}
      <div class="flex items-center justify-center py-12 gap-2 text-gray-400 text-sm">
        <svg class="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        Loading your foods...
      </div>
    {:else}
      <!-- Favorites -->
      {#if favorites.length > 0}
        <div class="mt-3">
          <div class="px-4 py-2">
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">⭐ Favorites</p>
          </div>
          <div class="bg-white">
            {#each favorites as uf (uf.id)}
              <ProfileFoodItem
                userFood={uf}
                on:openSheet={(e) => openSheet(e.detail)}
                on:edit={(e) => { editFood = e.detail; editVisible = true; }}
                on:delete={handleDelete}
              />
            {/each}
          </div>
        </div>
      {/if}

      <!-- Recent -->
      {#if recent.length > 0}
        <div class="mt-3">
          <div class="px-4 py-2">
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">🍽️ Your Foods</p>
          </div>
          <div class="bg-white">
            {#each recent as uf (uf.id)}
              <ProfileFoodItem
                userFood={uf}
                on:openSheet={(e) => openSheet(e.detail)}
                on:delete={handleDelete}
                on:edit={(e) => { editFood = e.detail; editVisible = true; }}
              />
            {/each}
          </div>
        </div>
      {/if}

      <!-- Empty state -->
      {#if favorites.length === 0 && recent.length === 0 && !loading}
        <div class="flex flex-col items-center justify-center py-16 px-8 text-center">
          <div class="text-5xl mb-4">🥗</div>
          <h3 class="font-semibold text-gray-800 text-lg mb-2">Your food library is empty</h3>
          <p class="text-gray-500 text-sm mb-6">
            Add foods from the USDA database or create your own custom foods to start logging.
          </p>
          <button type="button"
            on:click={() => navStore.goTo('add')}
            class="px-5 py-2.5 bg-primary-600 text-white rounded-xl font-semibold hover:bg-primary-700"
          >
            Add Your First Food →
          </button>
        </div>
      {:else}
        <div class="mt-4 mx-4 mb-8 p-4 bg-white rounded-xl border border-gray-200">
          <p class="text-sm text-gray-600 mb-3">Can't find what you're looking for?</p>
          <button type="button"
            on:click={() => navStore.goTo('add')}
            class="w-full py-2.5 border-2 border-primary-500 text-primary-600 rounded-xl font-semibold text-sm hover:bg-primary-50 active:bg-primary-100"
          >
            Search USDA Database →
          </button>
        </div>
      {/if}
    {/if}
  </div>

</div>

<!-- Quick log sheet (outside overflow container) -->
<QuickLogSheet
  userFood={sheetFood}
  visible={sheetVisible}
  on:log={handleLog}
  on:close={closeSheet}
/>

<EditFoodSheet
  userFood={editFood}
  visible={editVisible}
  on:saved={() => { editVisible = false; editFood = null; profileFoodsStore.refresh(); }}
  on:close={() => { editVisible = false; editFood = null; }}
/>
