import { apiRequest } from './client';
import type { FoodSearchResponse } from '../types/profile';

export async function searchFoods(q: string, limit = 20): Promise<FoodSearchResponse> {
  const qs = new URLSearchParams({ q, limit: String(limit) });
  return apiRequest<FoodSearchResponse>(`/foods/search?${qs}`);
}

export interface SummaryNutrient {
  name: string;
  value: number;
  unit: string;
}

export async function getFoodSummary(foodId: number, quantity: number): Promise<SummaryNutrient[]> {
  return apiRequest<SummaryNutrient[]>(`/foods/${foodId}/summary?quantity=${quantity}`);
}

export interface BatchSummaryRequest {
  food_id: number;
  quantity: number;
}

export async function getBatchFoodSummary(
  items: BatchSummaryRequest[]
): Promise<Record<string, SummaryNutrient[]>> {
  return apiRequest<Record<string, SummaryNutrient[]>>('/foods/batch-summary', {
    method: 'POST',
    body: JSON.stringify({ items }),
    headers: { 'Content-Type': 'application/json' },
  });
}
