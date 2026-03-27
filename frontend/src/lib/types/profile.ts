export interface FoodNutrient {
  nutrient: { id: number; name: string; unit: string };
  amount_per_serving: number;
}

export interface Portion {
  id: number;
  amount: number;
  unit_name: string | null;
  modifier: string | null;
  gram_weight: number;
  portion_description: string | null;
}

export interface FoodDetail {
  id: number;
  name: string;
  brand: string | null;
  serving_size: number;
  unit: string;
  created_by_user_id: number | null;
  food_nutrients: FoodNutrient[];
  portions: Portion[];
  calories?: number | null;
  protein?: number | null;
  carbs?: number | null;
  fat?: number | null;
}

export interface MealBasic {
  id: number;
  name: string;
}

export interface UserFood {
  id: number;
  user_id: number;
  food_id: number;
  nickname: string | null;
  default_quantity: number | null;
  default_unit: string | null;
  default_meal_id: number | null;
  is_favorite: boolean;
  use_count: number;
  last_used_at: string | null;
  created_at: string;
  updated_at: string;
  food: FoodDetail;
  default_meal: MealBasic | null;
}

export interface UserFoodListResponse {
  foods: UserFood[];
  total: number;
  limit: number;
  offset: number;
}

export interface DailyLogEntry {
  id: number;
  food_id: number;
  food_name: string;
  quantity: number;
  unit: string;
  logged_at: string;
  calories: number | null;
  protein: number | null;
  carbs: number | null;
  fat: number | null;
  fiber?: number | null;
  summary_nutrients?: Array<{ name: string; value: number; unit: string }>;
}

export interface MealGroup {
  meal: { id: number; name: string; display_order: number };
  logs: DailyLogEntry[];
}

export interface NutrientSummary {
  nutrient_id: number;
  name: string;
  value: number;
  target: number | null;
  unit: string;
}

export interface DailyLogResponse {
  date: string;
  meals: MealGroup[];
  summary: { nutrients: NutrientSummary[] };
}

export interface FoodSearchResultItem {
  id: number;
  name: string;
  brand: string | null;
  serving_size: number;
  unit: string;
  usda_fdc_id: number | null;
  similarity: number | null;
  calories: number | null;
  protein: number | null;
  carbs: number | null;
  fat: number | null;
  portions: Portion[];
}

export interface FoodSearchResponse {
  query: string;
  results: FoodSearchResultItem[];
  total: number;
  limit: number;
  offset: number;
}

/** Standard meals seeded in the database. IDs match seed order. */
export const STANDARD_MEALS: MealBasic[] = [
  { id: 1, name: 'Breakfast' },
  { id: 2, name: 'Lunch' },
  { id: 3, name: 'Dinner' },
  { id: 4, name: 'Snack' },
];

/** Extract calories from food_nutrients array (handles both USDA and custom). */
/** Returns kcal per gram for this food.
 * USDA foods: amount_per_serving is per 100g → divide by 100
 * Custom foods: amount_per_serving is per serving_size → divide by serving_size
 */
export function getFoodCalPerGram(food: FoodDetail): number | null {
  const n = food.food_nutrients?.find(fn =>
    fn.nutrient.name.toLowerCase().includes('energy')
  );
  if (!n) return null;
  let kcal = n.amount_per_serving;
  const base = food.created_by_user_id ? (food.serving_size || 100) : 100;
  return kcal / base;
}

/** Returns kcal for a specific gram weight. */
export function getFoodCalForGrams(food: FoodDetail, grams: number): number | null {
  const cpg = getFoodCalPerGram(food);
  return cpg !== null ? Math.round(cpg * grams) : null;
}

/** Returns kcal for the food's default serving. */
export function getFoodCalPerServing(food: FoodDetail): number | null {
  const cpg = getFoodCalPerGram(food);
  return cpg !== null ? Math.round(cpg * (food.serving_size || 100)) : null;
}

/** @deprecated Use getFoodCalPerGram */
export function getFoodCalPer100g(food: FoodDetail): number | null {
  // Legacy: returns kcal * base (not per 100g for custom foods)
  const cpg = getFoodCalPerGram(food);
  return cpg !== null ? cpg * 100 : null;
}

/** @deprecated */
export function getFoodCalories(food: FoodDetail): number | null {
  return getFoodCalPer100g(food);
}

/** Get display name for a UserFood (nickname or food.name). */
export function getDisplayName(uf: UserFood): string {
  return uf.nickname ?? uf.food.name;
}

/** Get default serving label e.g. "2 piece" or "100 g". 
 * 
 * Handles cases where default_unit already contains quantity prefix
 * to avoid duplication like "1 1 Bar" or "6 6 crackers".
 */
export function getServingLabel(uf: UserFood): string {
  const qty = uf.default_quantity ?? uf.food.serving_size;
  const unit = uf.default_unit ?? uf.food.unit;
  return `${qty} ${unit}`;
}
