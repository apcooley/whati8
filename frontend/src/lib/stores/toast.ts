import { writable } from 'svelte/store';

export interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

function createToastStore() {
  const { subscribe, update } = writable<Toast[]>([]);

  function remove(id: string) {
    update(toasts => toasts.filter(t => t.id !== id));
  }

  function add(message: string, type: Toast['type'] = 'success', duration = 3000) {
    const id = `${Date.now()}-${Math.random().toString(36).substr(2, 5)}`;
    update(toasts => [...toasts, { id, message, type }]);
    setTimeout(() => remove(id), duration);
  }

  return {
    subscribe,
    success: (msg: string) => add(msg, 'success'),
    error: (msg: string) => add(msg, 'error', 4000),
    info: (msg: string) => add(msg, 'info'),
    remove,
  };
}

export const toastStore = createToastStore();
