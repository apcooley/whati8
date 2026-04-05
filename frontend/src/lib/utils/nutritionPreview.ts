/**
 * Shared debounced nutrition preview.
 *
 * Creates a Svelte-compatible writable store that fetches summary nutrients
 * from the server whenever food ID or estimated grams change, debounced
 * at 200ms.  Used by QuickLogSheet, EditLogSheet, and RecipeIngredientRow.
 */

import { writable, type Writable } from 'svelte/store';
import { getFoodSummary, type SummaryNutrient } from '../api/foods';

export interface NutritionPreview {
  /** Subscribe to this store for the latest nutrients (or null while loading). */
  nutrients: Writable<SummaryNutrient[] | null>;
  /** Call when foodId or estGrams changes. Debounces the API call. */
  update: (foodId: number, estGrams: number) => void;
  /** Reset nutrients to null (e.g. when food changes). */
  clear: () => void;
  /** Cancel any pending timer. Call in onDestroy. */
  destroy: () => void;
}

const DEBOUNCE_MS = 200;

export function createNutritionPreview(): NutritionPreview {
  const nutrients = writable<SummaryNutrient[] | null>(null);
  let timer: ReturnType<typeof setTimeout> | null = null;

  function update(foodId: number, estGrams: number) {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      getFoodSummary(foodId, estGrams)
        .then(sn => nutrients.set(sn))
        .catch(() => nutrients.set(null));
    }, DEBOUNCE_MS);
  }

  function clear() {
    if (timer) clearTimeout(timer);
    nutrients.set(null);
  }

  function destroy() {
    if (timer) clearTimeout(timer);
  }

  return { nutrients, update, clear, destroy };
}
