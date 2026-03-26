import { writable, get } from 'svelte/store';
import type { DailyLogResponse } from '../types/profile';
import { getDailyLogs } from '../api/daily';

interface DailyLogsState {
  date: string;
  data: DailyLogResponse | null;
  loading: boolean;
  error: string | null;
}

function todayStr(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

function createDailyLogsStore() {
  const store = writable<DailyLogsState>({
    date: todayStr(),
    data: null,
    loading: false,
    error: null,
  });

  const { subscribe, update } = store;

  async function load(date?: string) {
    const targetDate = date ?? get(store).date;
    update(s => ({ ...s, loading: true, error: null, date: targetDate }));
    try {
      const data = await getDailyLogs(targetDate);
      update(s => ({ ...s, data, loading: false }));
    } catch (e) {
      update(s => ({
        ...s,
        loading: false,
        error: e instanceof Error ? e.message : 'Failed to load',
      }));
    }
  }

  return {
    subscribe,
    load,
    setDate: (date: string) => load(date),
    invalidate: () => load(get(store).date),
  };
}

export const dailyLogsStore = createDailyLogsStore();
