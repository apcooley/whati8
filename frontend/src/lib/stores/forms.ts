import { writable } from 'svelte/store';
import type { FormData } from '../types/chat';

interface FormState {
  visible: boolean;
  data: FormData | null;
}

function createFormStore() {
  const { subscribe, set, update } = writable<FormState>({
    visible: false,
    data: null,
  });

  return {
    subscribe,
    show(data: FormData) {
      set({ visible: true, data });
    },
    hide() {
      set({ visible: false, data: null });
    },
    submit(result: any) {
      // This would send the result back to the chat
      // For now, just hide the form
      set({ visible: false, data: null });
      return result;
    },
    cancel() {
      set({ visible: false, data: null });
    },
  };
}

export const formStore = createFormStore();
