import { writable } from 'svelte/store';
import type { UserFood } from '../types/profile';
import { getRecentFoods, listProfileFoods } from '../api/profile';

interface ProfileFoodsState {
  favorites: UserFood[];
  recent: UserFood[];
  loading: boolean;
  error: string | null;
}

function createProfileFoodsStore() {
  const { subscribe, update } = writable<ProfileFoodsState>({
    favorites: [],
    recent: [],
    loading: false,
    error: null,
  });

  async function load() {
    update(s => ({ ...s, loading: true, error: null }));
    try {
      const [favResult, recent] = await Promise.all([
        listProfileFoods({ sort: 'favorite', limit: 20 }),
        getRecentFoods(10),
      ]);
      const favorites = favResult.foods.filter(f => f.is_favorite);
      update(s => ({ ...s, favorites, recent, loading: false }));
    } catch (e) {
      update(s => ({
        ...s,
        loading: false,
        error: e instanceof Error ? e.message : 'Failed to load foods',
      }));
    }
  }

  async function search(q: string): Promise<UserFood[]> {
    try {
      const result = await listProfileFoods({ q, sort: 'recent', limit: 20 });
      return result.foods;
    } catch {
      return [];
    }
  }

  return {
    subscribe,
    load,
    search,
    invalidate: load,
  };
}

export const profileFoodsStore = createProfileFoodsStore();
