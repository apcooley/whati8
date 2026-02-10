import { writable } from 'svelte/store';

export interface FoodPortion {
  portion_id: number;
  amount: number;
  unit_name: string;
  modifier: string | null;
  gram_weight: number;
  display_name: string;
}

export interface MultiFoodItem {
  item_id: string;
  raw_text: string;
  parsed_quantity: number;
  parsed_unit: string;
  confidence: number;
  selected_food_id: number | null;
  selected_name: string | null;
  serving_size: number | null;
  serving_unit: string | null;
  calories: number | null;
  protein: number | null;
  fat: number | null;
  fiber: number | null;
  portions: FoodPortion[];  // Available household portions
  alternatives: Array<{
    food_id: number;
    name: string;
    serving_size: number;
    serving_unit: string;
    calories: number;
    protein: number;
    fat: number;
    fiber: number;
    portions?: FoodPortion[];
  }>;
  status: 'matched' | 'not_found' | 'ambiguous';
}

interface MultiFoodFormState {
  items: MultiFoodItem[];
  selectedMeal: string;
  isSubmitting: boolean;
  error: string | null;
}

function createMultiFoodFormStore() {
  const { subscribe, set, update } = writable<MultiFoodFormState>({
    items: [],
    selectedMeal: 'Breakfast',
    isSubmitting: false,
    error: null,
  });

  return {
    subscribe,
    initialize(items: MultiFoodItem[], guessedMeal: string | null) {
      set({
        items,
        selectedMeal: guessedMeal || 'Breakfast',
        isSubmitting: false,
        error: null,
      });
    },
    addItem(item: MultiFoodItem) {
      update(state => ({
        ...state,
        items: [...state.items, item],
      }));
    },
    updateItem(itemId: string, updates: Partial<MultiFoodItem>) {
      update(state => ({
        ...state,
        items: state.items.map(item =>
          item.item_id === itemId ? { ...item, ...updates } : item
        ),
      }));
    },
    removeItem(itemId: string) {
      update(state => ({
        ...state,
        items: state.items.filter(item => item.item_id !== itemId),
      }));
    },
    setMeal(meal: string) {
      update(state => ({
        ...state,
        selectedMeal: meal,
      }));
    },
    setSubmitting(isSubmitting: boolean) {
      update(state => ({
        ...state,
        isSubmitting,
      }));
    },
    setError(error: string | null) {
      update(state => ({
        ...state,
        error,
      }));
    },
    reset() {
      set({
        items: [],
        selectedMeal: 'Breakfast',
        isSubmitting: false,
        error: null,
      });
    },
  };
}

export const multiFoodFormStore = createMultiFoodFormStore();
