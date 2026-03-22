import { apiRequest } from './client';
import type { FoodSearchResponse } from '../types/profile';

export async function searchFoods(q: string, limit = 20): Promise<FoodSearchResponse> {
  const qs = new URLSearchParams({ q, limit: String(limit) });
  return apiRequest<FoodSearchResponse>(`/foods/search?${qs}`);
}
