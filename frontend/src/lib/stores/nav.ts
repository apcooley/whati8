import { writable } from 'svelte/store';

export type Tab = 'log' | 'today' | 'add' | 'chat';

interface NavState {
  activeTab: Tab;
  pendingQuery: string | undefined;
}

function createNavStore() {
  const { subscribe, set, update } = writable<NavState>({
    activeTab: 'log',
    pendingQuery: undefined,
  });

  return {
    subscribe,
    goTo(tab: Tab, opts?: { query?: string }) {
      set({ activeTab: tab, pendingQuery: opts?.query });
    },
    clearPending() {
      update(s => ({ ...s, pendingQuery: undefined }));
    },
  };
}

export const navStore = createNavStore();
