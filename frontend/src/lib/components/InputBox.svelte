<script lang="ts">
  import { chatStore } from '../stores/chat';

  let message = '';
  let textarea: HTMLTextAreaElement;

  $: loading = $chatStore.loading;

  async function handleSubmit() {
    if (!message.trim() || loading) return;

    const text = message;
    message = '';

    // Reset textarea height
    if (textarea) {
      textarea.style.height = 'auto';
    }

    try {
      await chatStore.sendMessage(text);
    } catch (error) {
      console.error('Failed to send message:', error);
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  }

  function autoResize() {
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 96) + 'px';
    }
  }
</script>

<div class="border-t border-gray-200 bg-white p-4">
  <form on:submit|preventDefault={handleSubmit} class="flex gap-2">
    <textarea
      bind:this={textarea}
      bind:value={message}
      on:keydown={handleKeydown}
      on:input={autoResize}
      disabled={loading}
      placeholder="Type a message... (Shift+Enter for new line)"
      rows="1"
      class="flex-1 resize-none rounded-lg border border-gray-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
      style="max-height: 96px;"
    />
    <button
      type="submit"
      disabled={!message.trim() || loading}
      class="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed min-h-[44px]"
    >
      <svg
        class="w-5 h-5"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
        />
      </svg>
    </button>
  </form>
</div>
