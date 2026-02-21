<script lang="ts">
  import { chatStore } from '../stores/chat';
  import MessageBubble from './MessageBubble.svelte';
  import { onMount, afterUpdate } from 'svelte';

  let messageContainer: HTMLDivElement;

  function scrollToBottom() {
    if (messageContainer) {
      messageContainer.scrollTop = messageContainer.scrollHeight;
    }
  }

  afterUpdate(() => {
    scrollToBottom();
  });

  onMount(() => {
    scrollToBottom();
  });

  $: messages = $chatStore.messages;
</script>

<div
  bind:this={messageContainer}
  class="flex-1 overflow-y-auto p-4 space-y-2"
>
  {#if messages.length === 0}
    <div class="flex items-center justify-center h-full text-gray-500">
      <div class="text-center">
        <h3 class="text-lg font-medium mb-2">Start a conversation</h3>
        <p class="text-sm">Try saying "I had 2 eggs for breakfast"</p>
      </div>
    </div>
  {:else}
    {#each messages as message (message.timestamp)}
      <MessageBubble {message} />
    {/each}
  {/if}

  {#if $chatStore.loading}
    <div class="flex justify-start">
      <div class="bg-white text-gray-900 border border-gray-200 rounded-lg px-4 py-2">
        <div class="flex space-x-2">
          <div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0ms"></div>
          <div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 150ms"></div>
          <div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 300ms"></div>
        </div>
      </div>
    </div>
  {/if}

  {#if $chatStore.error}
    <div class="bg-red-50 text-red-700 p-3 rounded-md text-sm">
      Error: {$chatStore.error}
    </div>
  {/if}
</div>
