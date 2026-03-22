<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { recognizePhoto, type RecognitionResult } from '../api/photo';
  import { toastStore } from '../stores/toast';

  const dispatch = createEventDispatcher<{
    result: RecognitionResult;
    close: void;
  }>();

  let cameraInput: HTMLInputElement;
  let uploadInput: HTMLInputElement;
  let loading = false;
  let preview: string | null = null;

  function openCamera() {
    cameraInput?.click();
  }

  function openUpload() {
    uploadInput?.click();
  }

  async function handleFile(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    preview = URL.createObjectURL(file);
    loading = true;

    try {
      const result = await recognizePhoto(file);
      dispatch('result', result);
    } catch (err) {
      toastStore.error(err instanceof Error ? err.message : 'Recognition failed');
    } finally {
      loading = false;
      if (preview) {
        URL.revokeObjectURL(preview);
        preview = null;
      }
      input.value = '';
    }
  }
</script>

<!-- Camera input (opens camera on mobile) -->
<input
  type="file"
  accept="image/*"
  capture="environment"
  bind:this={cameraInput}
  on:change={handleFile}
  class="hidden"
/>

<!-- Upload input (opens file picker / gallery) -->
<input
  type="file"
  accept="image/*"
  bind:this={uploadInput}
  on:change={handleFile}
  class="hidden"
/>

{#if loading}
  <div class="fixed inset-0 bg-black bg-opacity-60 z-50 flex flex-col items-center justify-center gap-4">
    {#if preview}
      <img src={preview} alt="Analyzing..." class="w-48 h-48 object-cover rounded-2xl opacity-80" />
    {/if}
    <div class="flex items-center gap-3 text-white">
      <svg class="animate-spin h-6 w-6" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      <span class="text-lg font-medium">Analyzing food...</span>
    </div>
  </div>
{/if}

<div class="grid grid-cols-2 gap-2">
  <button type="button"
    on:click={openCamera}
    disabled={loading}
    class="py-3 px-4 bg-white border border-gray-200 rounded-xl text-sm text-left flex items-center gap-3 hover:bg-gray-50 active:bg-gray-100 disabled:opacity-50"
  >
    <span class="text-2xl">📷</span>
    <div>
      <p class="font-medium text-gray-900">Take Photo</p>
      <p class="text-xs text-gray-500">Use camera</p>
    </div>
  </button>

  <button type="button"
    on:click={openUpload}
    disabled={loading}
    class="py-3 px-4 bg-white border border-gray-200 rounded-xl text-sm text-left flex items-center gap-3 hover:bg-gray-50 active:bg-gray-100 disabled:opacity-50"
  >
    <span class="text-2xl">🖼️</span>
    <div>
      <p class="font-medium text-gray-900">Upload Photo</p>
      <p class="text-xs text-gray-500">From gallery</p>
    </div>
  </button>
</div>
