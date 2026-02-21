import { writable } from 'svelte/store';
import type { User } from '../types/chat';
import { register as apiRegister, login as apiLogin, getMe } from '../api/agent';

interface AuthState {
  token: string | null;
  user: User | null;
  loading: boolean;
}

function createAuthStore() {
  const { subscribe, set, update } = writable<AuthState>({
    token: localStorage.getItem('token'),
    user: null,
    loading: false,
  });

  return {
    subscribe,
    async register(username: string, email: string, password: string) {
      update(state => ({ ...state, loading: true }));
      try {
        const user = await apiRegister(username, email, password);
        // After registration, log in automatically
        const response = await apiLogin(username, password);
        localStorage.setItem('token', response.access_token);
        update(state => ({
          ...state,
          token: response.access_token,
          user,
          loading: false,
        }));
      } catch (error) {
        update(state => ({ ...state, loading: false }));
        throw error;
      }
    },
    async login(username: string, password: string) {
      update(state => ({ ...state, loading: true }));
      try {
        const response = await apiLogin(username, password);
        localStorage.setItem('token', response.access_token);
        const user = await getMe();
        update(state => ({
          ...state,
          token: response.access_token,
          user,
          loading: false,
        }));
      } catch (error) {
        update(state => ({ ...state, loading: false }));
        throw error;
      }
    },
    logout() {
      localStorage.removeItem('token');
      set({ token: null, user: null, loading: false });
    },
    async loadUser() {
      const token = localStorage.getItem('token');
      if (!token) return;

      update(state => ({ ...state, loading: true }));
      try {
        const user = await getMe();
        update(state => ({ ...state, token, user, loading: false }));
      } catch (error) {
        // Token invalid, clear it
        localStorage.removeItem('token');
        update(state => ({ ...state, token: null, loading: false }));
      }
    },
  };
}

export const authStore = createAuthStore();
