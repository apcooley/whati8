import { writable, get } from 'svelte/store';
import type { Message } from '../types/chat';
import { sendChatMessage } from '../api/agent';
import { formStore } from './forms';

interface ChatState {
  messages: Message[];
  sessionId: string;
  loading: boolean;
  error: string | null;
}

function generateSessionId(): string {
  return `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

function createChatStore() {
  const store = writable<ChatState>({
    messages: [],
    sessionId: generateSessionId(),
    loading: false,
    error: null,
  });

  const { subscribe, set, update } = store;

  return {
    subscribe,
    async sendMessage(content: string) {
      // Add user message
      update(state => {
        const userMessage: Message = {
          role: 'user',
          content,
          timestamp: new Date(),
        };
        return {
          ...state,
          messages: [...state.messages, userMessage],
          loading: true,
          error: null,
        };
      });

      try {
        // Get current session ID using get()
        const currentSessionId = get(store).sessionId;

        // Get user's timezone
        const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

        const response = await sendChatMessage({
          message: content,
          session_id: currentSessionId,
          user_timezone: userTimezone,
        });

        // Ensure loading is cleared and message is added
        update(state => {
          const assistantMessage: Message = {
            role: 'assistant',
            content: response.message || 'No response',
            timestamp: new Date(), // Always use local time
            toolResults: response.tool_results || undefined,
          };
          return {
            ...state,
            messages: [...state.messages, assistantMessage],
            loading: false,
            error: null,
          };
        });

        // Show form if required
        if (response.requires_form && response.form_data) {
          formStore.show(response.form_data);
        }

        return response;
      } catch (error) {
        console.error('Chat error:', error);
        update(state => ({
          ...state,
          loading: false,
          error: error instanceof Error ? error.message : 'Unknown error',
        }));
        throw error;
      }
    },
    clearHistory() {
      set({
        messages: [],
        sessionId: generateSessionId(),
        loading: false,
        error: null,
      });
    },
  };
}

export const chatStore = createChatStore();
