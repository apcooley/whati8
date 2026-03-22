<script lang="ts">
  import { formStore } from '../stores/forms';
  import { chatStore } from '../stores/chat';
  import MultiFoodForm from './MultiFoodForm.svelte';

  $: visible = $formStore.visible;
  $: data = $formStore.data;

  function handleClose() {
    formStore.cancel();
  }

  function handleSubmit(selection: any) {
    formStore.submit(selection);
    // Send confirmation back to chat
    chatStore.sendMessage(`Confirmed: ${JSON.stringify(selection)}`);
  }
</script>

{#if visible && data}
  {#if data.form_type === 'multi_food_confirmation'}
    <MultiFoodForm data={data.data} onClose={handleClose} />
  {:else}
    <div class="fixed inset-0 bg-black bg-opacity-50 flex items-end md:items-center justify-center z-50">
      <!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
      <!-- Backdrop -->
      <div 
        class="absolute inset-0" 
        on:click={handleClose}
        on:keydown={(e) => e.key === 'Escape' && handleClose()}
        role="button"
        tabindex="-1"
        aria-label="Close modal"
      ></div>

      <!-- Modal -->
      <div
        class="relative bg-white rounded-t-lg md:rounded-lg shadow-xl w-full md:max-w-md md:mx-4 max-h-[80vh] overflow-y-auto"
      >
        <!-- Header -->
        <div class="sticky top-0 bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
          <h3 class="text-lg font-semibold text-gray-900">
            {data.form_type === 'food_selection' ? 'Select Food' : 'Confirm Log Entry'}
          </h3>
          <button type="button"
            on:click={handleClose}
            class="text-gray-400 hover:text-gray-600"
          >
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Content -->
        <div class="p-4">
          {#if data.form_type === 'food_selection'}
            <p class="text-sm text-gray-600 mb-4">Select the food you want to log:</p>
            <div class="space-y-2">
              {#each data.data.foods || [] as food}
                <button type="button"
                  on:click={() => handleSubmit({ food_id: food.id, food_name: food.name })}
                  class="w-full text-left p-4 border-2 border-gray-200 rounded-lg hover:border-primary-500 hover:bg-primary-50 focus:outline-none focus:ring-2 focus:ring-primary-500 transition-colors"
                >
                  <div class="font-medium text-gray-900">
                    {food.name}
                    {#if food.serving_size && food.unit}
                      <span class="text-sm font-normal text-gray-600 ml-2">({food.serving_size}{food.unit})</span>
                    {/if}
                  </div>
                  {#if food.brand}
                    <div class="text-sm text-gray-600 mt-1">{food.brand}</div>
                  {/if}
                  <div class="text-sm text-gray-500 mt-2 flex gap-4">
                    {#if food.calories}
                      <span class="font-medium">{food.calories} cal</span>
                    {/if}
                    {#if food.protein}
                      <span>{food.protein}g protein</span>
                    {/if}
                  </div>
                </button>
              {/each}
            </div>
          {:else if data.form_type === 'log_confirmation'}
            <div class="space-y-4">
              <div>
                <div class="text-sm text-gray-600">Food</div>
                <div class="font-medium">{data.data.food_name}</div>
              </div>
              <div>
                <div class="text-sm text-gray-600">Quantity</div>
                <div class="font-medium">{data.data.quantity}g</div>
              </div>
              {#if data.data.meal}
                <div>
                  <div class="text-sm text-gray-600">Meal</div>
                  <div class="font-medium">{data.data.meal}</div>
                </div>
              {/if}

              <div class="flex gap-2 pt-4">
                <button type="button"
                  on:click={handleClose}
                  class="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button type="button"
                  on:click={() => handleSubmit({ confirmed: true })}
                  class="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
                >
                  Confirm
                </button>
              </div>
            </div>
          {/if}
        </div>
      </div>
    </div>
  {/if}
{/if}
