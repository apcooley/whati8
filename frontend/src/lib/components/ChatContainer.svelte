<script lang="ts">
  import { authStore } from '../stores/auth';
  import { chatStore } from '../stores/chat';
  import LoginModal from './LoginModal.svelte';
  import MessageList from './MessageList.svelte';
  import InputBox from './InputBox.svelte';
  import FormModal from './FormModal.svelte';

  /** When true, hides the standalone header/shell (for embedding inside NavShell). */
  export let embedded = false;

  $: authenticated = $authStore.token !== null;
  $: user = $authStore.user;

  function handleLogout() {
    authStore.logout();
    chatStore.clearHistory();
  }

  function handleClearHistory() {
    if (confirm('Clear conversation history?')) {
      chatStore.clearHistory();
    }
  }
</script>

{#if embedded}
  <!-- Embedded mode: just chat content, no outer shell -->
  <div class="flex flex-col h-full bg-gray-50">
    <div class="flex items-center justify-between px-4 py-2 border-b border-gray-200 bg-white flex-shrink-0">
      <span class="text-sm text-gray-500">AI Food Assistant</span>
      {#if authenticated}
        <button type="button"
          on:click={handleClearHistory}
          class="p-1.5 text-gray-400 hover:text-gray-600 rounded"
          title="Clear history"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
      {/if}
    </div>
    <div class="flex-1 overflow-hidden flex flex-col">
      <MessageList />
      <InputBox />
    </div>
    <FormModal />
  </div>
{:else}
  <div class="flex flex-col h-screen bg-gray-50">
    <!-- Header -->
    <header class="bg-primary-600 text-white shadow-md">
      <div class="px-4 py-3 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <h1 class="text-xl font-bold">whati8</h1>
          {#if user}
            <span class="text-sm text-primary-100">@{user.username}</span>
          {/if}
        </div>
        <div class="flex gap-2">
          {#if authenticated}
            <button type="button"
              on:click={handleClearHistory}
              class="px-3 py-1 text-sm bg-primary-700 hover:bg-primary-800 rounded"
              title="Clear history"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
            <button type="button"
              on:click={handleLogout}
              class="px-3 py-1 text-sm bg-primary-700 hover:bg-primary-800 rounded"
            >
              Logout
            </button>
          {/if}
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="flex-1 overflow-hidden flex flex-col">
      {#if authenticated}
        <MessageList />
        <InputBox />
      {:else}
        <div class="flex-1 flex items-center justify-center p-4">
          <div class="text-center text-gray-600">
            <h2 class="text-2xl font-bold mb-2">Welcome to whati8</h2>
            <p>Sign in to start tracking your food</p>
          </div>
        </div>
      {/if}
    </main>

    <!-- Modals -->
    {#if !authenticated}
      <LoginModal />
    {/if}

    <FormModal />
  </div>
{/if}
