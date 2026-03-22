<script lang="ts">
  import { onMount } from 'svelte';
  import type { FoodSearchResultItem } from '../types/profile';
  import { navStore } from '../stores/nav';
  import { profileFoodsStore } from '../stores/profileFoods';
  import { toastStore } from '../stores/toast';
  import { registerFood, updateUserFood, listProfileFoods } from '../api/profile';
  import { apiRequest } from '../api/client';
  import USDASearch from './USDASearch.svelte';
  import ManualFoodForm from './ManualFoodForm.svelte';
  import RegisterSheet from './RegisterSheet.svelte';
  import PhotoCapture from './PhotoCapture.svelte';
  import PhotoResults from './PhotoResults.svelte';
  import RecipeBuilder from './RecipeBuilder.svelte';
  import type { RecognitionResult } from '../api/photo';
  import type { Recipe } from '../api/recipe';

  let mode: 'search' | 'manual' | 'recipe' = 'search';
  let photoResult: RecognitionResult | null = null;
  let selectedFood: FoodSearchResultItem | null = null;
  let sheetVisible = false;
  let initialQuery = '';

  // "Already exists" dialog state
  let existsDialogVisible = false;
  let existingUserFoodId: number | null = null;
  let pendingRegisterData: any = null;

  onMount(() => {
    const pending = $navStore.pendingQuery;
    if (pending !== undefined) {
      initialQuery = pending;
      navStore.clearPending();
    }
  });

  function handlePhotoResult(e: CustomEvent<RecognitionResult>) {
    photoResult = e.detail;
  }

  async function handlePhotoSave(e: CustomEvent<{ item: any; custom_unit: string | null; default_quantity: number; weight_per_unit: number; volume_ml: number | null }>) {
    const { item, custom_unit, default_quantity, weight_per_unit, volume_ml } = e.detail;
    try {
      const n = item.nutrients || {};
      const servingG = item.serving_size_g || 100;
      const payload: Record<string, any> = {
        name: item.name || 'Unknown Food',
        serving_size: servingG,
        unit: custom_unit || 'g',
        gram_weight: servingG,
        serving_description: item.serving_description,
        calories: Number(n.calories) || 0,
        protein: Number(n.protein_g) || 0,
        carbs: Number(n.carbs_g) || 0,
        fat: Number(n.fat_g) || 0,
        fiber: Number(n.fiber_g) || 0,
      };
      if (custom_unit) payload.custom_unit = custom_unit;
      if (default_quantity > 1) payload.serving_quantity = default_quantity;
      if (volume_ml) payload.volume_ml = volume_ml;

      const food = await apiRequest<any>('/foods/', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      await registerFood({
        food_id: food.id,
        default_quantity: default_quantity || 1,
        default_unit: item.serving_description,  // portion label e.g. "bottle (325g)"
      });
      toastStore.success(`Added "${item.name}"`);
      profileFoodsStore.invalidate();
      photoResult = null;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to add food';
      if (msg.toLowerCase().includes('already')) {
        toastStore.info(msg);
        photoResult = null;
      } else {
        toastStore.error(msg);
      }
    }
  }

  $: {
    const pending = $navStore.pendingQuery;
    if (pending !== undefined && pending !== initialQuery) {
      initialQuery = pending;
      navStore.clearPending();
      mode = 'search';
    }
  }

  function handleFoodSelect(e: CustomEvent<FoodSearchResultItem>) {
    selectedFood = e.detail;
    sheetVisible = true;
  }

  async function handleRegister(e: CustomEvent<any>) {
    sheetVisible = false;
    try {
      const uf = await registerFood(e.detail);
      const name = uf.nickname ?? uf.food.name;
      toastStore.success(`Added "${name}" to your foods`);
      profileFoodsStore.invalidate();
      navStore.goTo('log');
    } catch (err: any) {
      const msg = err?.message ?? '';
      if (msg.toLowerCase().includes('already')) {
        // Food already registered — show dialog
        pendingRegisterData = e.detail;
        // Find the existing user_food id
        try {
          const existing = await listProfileFoods({ q: selectedFood?.name ?? '' });
          const match = existing.foods.find(f => f.food_id === e.detail.food_id);
          existingUserFoodId = match?.id ?? null;
        } catch { existingUserFoodId = null; }
        existsDialogVisible = true;
      } else {
        toastStore.error(msg || 'Failed to register food');
      }
    }
  }

  async function handleOverwrite() {
    existsDialogVisible = false;
    if (!existingUserFoodId || !pendingRegisterData) return;
    try {
      await updateUserFood(existingUserFoodId, {
        nickname: pendingRegisterData.nickname,
        default_quantity: pendingRegisterData.default_quantity,
        default_unit: pendingRegisterData.default_unit,
        default_meal_id: pendingRegisterData.default_meal_id,
        is_favorite: pendingRegisterData.is_favorite,
      });
      toastStore.success('Updated food settings');
      profileFoodsStore.invalidate();
      navStore.goTo('log');
    } catch (err: any) {
      toastStore.error(err?.message ?? 'Failed to update');
    }
    pendingRegisterData = null;
    existingUserFoodId = null;
  }

  function handleRename() {
    existsDialogVisible = false;
    // Re-open the register sheet so user can set a nickname
    if (selectedFood) {
      sheetVisible = true;
    }
  }

  function handleCancelExists() {
    existsDialogVisible = false;
    pendingRegisterData = null;
    existingUserFoodId = null;
  }

  function handleManualCreated(e: CustomEvent<any>) {
    const food: FoodSearchResultItem = {
      id: e.detail.id,
      name: e.detail.name,
      brand: e.detail.brand ?? null,
      serving_size: e.detail.serving_size,
      unit: e.detail.unit,
      usda_fdc_id: null,
      similarity: null,
      calories: e.detail.calories,
      protein: e.detail.protein,
      carbs: e.detail.carbs,
      fat: e.detail.fat,
      portions: [],
    };
    mode = 'search';
    selectedFood = food;
    sheetVisible = true;
  }

  async function handleRecipeSaved(e: CustomEvent<Recipe>) {
    const recipe = e.detail;
    toastStore.success(`Recipe "${recipe.name}" saved!`);
    profileFoodsStore.invalidate();
    mode = 'search';
    navStore.goTo('log');
  }
</script>

<div class="flex flex-col h-full overflow-hidden bg-gray-50">
  <!-- Header -->
  <div class="flex-shrink-0 bg-white border-b border-gray-200 px-4 py-4">
    <h2 class="text-lg font-bold text-gray-900">Add to Your Foods</h2>
    <p class="text-sm text-gray-500 mt-0.5">Search USDA or enter manually</p>
  </div>

  <!-- Tab switcher -->
  <div class="flex-shrink-0 bg-white px-4 py-3 border-b border-gray-200 flex gap-2">
    <button type="button"
      on:click={() => mode = 'search'}
      class="flex-1 py-2 rounded-xl text-sm font-semibold transition-colors
        {mode === 'search' ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}"
    >
      🔍 Search
    </button>
    <button type="button"
      on:click={() => mode = 'manual'}
      class="flex-1 py-2 rounded-xl text-sm font-semibold transition-colors
        {mode === 'manual' ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}"
    >
      ✏️ Manual
    </button>
    <button type="button"
      on:click={() => mode = 'recipe'}
      class="flex-1 py-2 rounded-xl text-sm font-semibold transition-colors
        {mode === 'recipe' ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}"
    >
      🍳 Recipe
    </button>
  </div>

  <!-- Content -->
  <div class="flex-1 overflow-y-auto">
    {#if mode === 'search'}
      <div class="p-4">
        <USDASearch {initialQuery} on:select={handleFoodSelect} />
      </div>

      <div class="mx-4 mb-6 space-y-2">
        <PhotoCapture on:result={handlePhotoResult} />
        
        <button type="button" on:click={() => mode = 'recipe'} class="w-full py-3 px-4 bg-white border border-gray-200 rounded-xl text-sm text-left flex items-center gap-3 hover:bg-gray-50">
          <span class="text-2xl">🍳</span>
          <div><p class="font-medium text-gray-900">Create Recipe</p><p class="text-xs text-gray-500">Combine foods into a recipe</p></div>
        </button>
        
        {#if photoResult}
          <PhotoResults
            items={photoResult.items}
            on:save={handlePhotoSave}
            on:close={() => photoResult = null}
          />
        {/if}
        <button type="button" disabled class="w-full py-3 px-4 bg-white border border-gray-200 rounded-xl text-sm text-gray-400 text-left flex items-center gap-3 cursor-not-allowed">
          <span class="text-2xl">📱</span>
          <div><p class="font-medium">Scan Barcode</p><p class="text-xs">Coming soon</p></div>
        </button>
      </div>
    {:else if mode === 'manual'}
      <div class="p-4">
        <ManualFoodForm on:created={handleManualCreated} on:cancel={() => mode = 'search'} />
      </div>
    {:else if mode === 'recipe'}
      <RecipeBuilder
        recipeId={null}
        prefillLines={[]}
        on:saved={handleRecipeSaved}
        on:close={() => mode = 'search'}
      />
    {/if}
  </div>

  <!-- Register sheet -->
  <RegisterSheet
    food={selectedFood}
    visible={sheetVisible}
    on:register={handleRegister}
    on:close={() => { sheetVisible = false; selectedFood = null; }}
  />

  <!-- "Already exists" dialog -->
  {#if existsDialogVisible}
    <div class="fixed inset-0 bg-black bg-opacity-40 z-50 flex items-center justify-center p-4"
      on:click={handleCancelExists} on:keydown={(e) => e.key === 'Escape' && handleCancelExists()} role="button" tabindex="-1" aria-label="Close">
      <div class="bg-white rounded-2xl shadow-xl max-w-sm w-full p-6" on:click|stopPropagation on:keydown|stopPropagation role="dialog" aria-modal="true">
        <h3 class="text-lg font-bold text-gray-900 mb-2">Food Already Added</h3>
        <p class="text-sm text-gray-600 mb-6">
          <span class="font-medium">{selectedFood?.name}</span> is already in your foods. What would you like to do?
        </p>
        <div class="flex flex-col gap-2">
          <button type="button" on:click={handleOverwrite}
            class="w-full py-3 bg-primary-600 text-white rounded-xl font-semibold hover:bg-primary-700 active:bg-primary-800">
            Overwrite Settings
          </button>
          <button type="button" on:click={handleRename}
            class="w-full py-3 bg-gray-100 text-gray-700 rounded-xl font-semibold hover:bg-gray-200">
            Add with Nickname
          </button>
          <button type="button" on:click={handleCancelExists}
            class="w-full py-3 text-gray-500 text-sm hover:text-gray-700">
            Cancel
          </button>
        </div>
      </div>
    </div>
  {/if}
</div>
