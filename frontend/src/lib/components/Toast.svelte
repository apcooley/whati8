<script lang="ts">
  import { toastStore } from '../stores/toast';
</script>

{#if $toastStore.length > 0}
  <div class="fixed top-4 left-0 right-0 z-50 flex flex-col items-center gap-2 pointer-events-none px-4">
    {#each $toastStore as toast (toast.id)}
      <div
        class="pointer-events-auto max-w-sm w-full px-4 py-3 rounded-lg shadow-lg text-sm font-medium flex items-center gap-3 animate-fade-in
          {toast.type === 'success' ? 'bg-green-600 text-white' :
           toast.type === 'error' ? 'bg-red-600 text-white' :
           'bg-gray-800 text-white'}"
      >
        {#if toast.type === 'success'}
          <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>
        {:else if toast.type === 'error'}
          <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        {:else}
          <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        {/if}
        <span class="flex-1">{toast.message}</span>
        <button type="button"
          on:click={() => toastStore.remove(toast.id)}
          class="flex-shrink-0 opacity-75 hover:opacity-100"
          aria-label="Dismiss"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    {/each}
  </div>
{/if}

<style>
  @keyframes fade-in {
    from { opacity: 0; transform: translateY(-8px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .animate-fade-in {
    animation: fade-in 0.2s ease-out;
  }
</style>
