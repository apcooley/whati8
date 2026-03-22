<script lang="ts">
  import { authStore } from '../stores/auth';
  import { chatStore } from '../stores/chat';
  import { navStore, type Tab } from '../stores/nav';
  import LoginModal from './LoginModal.svelte';
  import FormModal from './FormModal.svelte';
  import Toast from './Toast.svelte';
  import LogFoodView from './LogFoodView.svelte';
  import DailyLogsView from './DailyLogsView.svelte';
  import AddFoodView from './AddFoodView.svelte';
  import ChatContainer from './ChatContainer.svelte';

  $: authenticated = $authStore.token !== null;
  $: user = $authStore.user;
  $: activeTab = $navStore.activeTab;

  const tabs: { id: Tab; label: string; emoji: string }[] = [
    { id: 'log', label: 'Log', emoji: '📝' },
    { id: 'today', label: 'Today', emoji: '📋' },
    { id: 'add', label: 'Add', emoji: '➕' },
    { id: 'chat', label: 'Chat', emoji: '🤖' },
  ];

  function handleLogout() {
    authStore.logout();
    chatStore.clearHistory();
  }
</script>

<div class="flex flex-col h-screen bg-gray-50 max-w-lg mx-auto relative">
  <!-- Toast notifications (above everything) -->
  <Toast />

  <!-- App header -->
  <header class="flex-shrink-0 bg-primary-600 text-white shadow-md z-10">
    <div class="px-4 py-3 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <h1 class="text-xl font-bold">whati8</h1>
        {#if user}
          <span class="text-sm text-primary-100">@{user.username}</span>
        {/if}
      </div>
      {#if authenticated}
        <button type="button"
          on:click={handleLogout}
          class="px-3 py-1 text-sm bg-primary-700 hover:bg-primary-800 rounded"
        >
          Logout
        </button>
      {/if}
    </div>
  </header>

  <!-- Main content area -->
  <main class="flex-1 overflow-hidden">
    {#if authenticated}
      <!-- Tab panels - all mounted, just hidden when not active for state preservation -->
      <div class="h-full" class:hidden={activeTab !== 'log'}>
        <LogFoodView />
      </div>
      <div class="h-full" class:hidden={activeTab !== 'today'}>
        <DailyLogsView />
      </div>
      <div class="h-full" class:hidden={activeTab !== 'add'}>
        <AddFoodView />
      </div>
      <div class="h-full" class:hidden={activeTab !== 'chat'}>
        <ChatContainer embedded={true} />
      </div>
    {:else}
      <div class="flex-1 flex items-center justify-center p-8 text-center text-gray-600 h-full">
        <div>
          <div class="text-6xl mb-4">🥗</div>
          <h2 class="text-2xl font-bold mb-2">Welcome to whati8</h2>
          <p>Sign in to start tracking your food</p>
        </div>
      </div>
    {/if}
  </main>

  <!-- Bottom tab bar -->
  {#if authenticated}
    <nav class="flex-shrink-0 bg-white border-t border-gray-200 shadow-lg z-10">
      <div class="flex">
        {#each tabs as tab}
          <button type="button"
            on:click={() => navStore.goTo(tab.id)}
            class="flex-1 flex flex-col items-center gap-0.5 py-2.5 transition-colors
              {activeTab === tab.id
                ? 'text-primary-600'
                : 'text-gray-500 hover:text-gray-700'}"
            aria-label={tab.label}
            aria-current={activeTab === tab.id ? 'page' : undefined}
          >
            <span class="text-xl leading-none">{tab.emoji}</span>
            <span class="text-xs font-medium">{tab.label}</span>
            {#if activeTab === tab.id}
              <span class="w-1 h-1 rounded-full bg-primary-600 mt-0.5"></span>
            {/if}
          </button>
        {/each}
      </div>
    </nav>
  {/if}

  <!-- Modals -->
  {#if !authenticated}
    <LoginModal />
  {/if}
  <FormModal />
</div>
