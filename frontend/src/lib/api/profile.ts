import { apiRequest } from './client';
import type { UserFood, UserFoodListResponse } from '../types/profile';

export interface ListProfileFoodsParams {
  q?: string;
  sort?: 'recent' | 'frequent' | 'alpha' | 'favorite';
  limit?: number;
  offset?: number;
}

export async function listProfileFoods(
  params: ListProfileFoodsParams = {}
): Promise<UserFoodListResponse> {
  const qs = new URLSearchParams();
  if (params.q) qs.set('q', params.q);
  if (params.sort) qs.set('sort', params.sort);
  if (params.limit != null) qs.set('limit', String(params.limit));
  if (params.offset != null) qs.set('offset', String(params.offset));
  const query = qs.toString();
  return apiRequest<UserFoodListResponse>(`/profile/foods${query ? `?${query}` : ''}`);
}

export async function getRecentFoods(limit = 10): Promise<UserFood[]> {
  return apiRequest<UserFood[]>(`/profile/foods/recent?limit=${limit}`);
}

export async function getFrequentFoods(limit = 10): Promise<UserFood[]> {
  return apiRequest<UserFood[]>(`/profile/foods/frequent?limit=${limit}`);
}

export async function searchProfileFoods(q: string, limit = 20): Promise<UserFood[]> {
  return apiRequest<UserFood[]>(`/profile/foods/search?q=${encodeURIComponent(q)}&limit=${limit}`);
}

export interface RegisterFoodPayload {
  food_id: number;
  nickname?: string | null;
  default_quantity?: number | null;
  default_unit?: string | null;
  default_meal_id?: number | null;
  is_favorite?: boolean;
}

export async function registerFood(data: RegisterFoodPayload): Promise<UserFood> {
  return apiRequest<UserFood>('/profile/foods/register', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export interface UpdateFoodPayload {
  nickname?: string | null;
  default_quantity?: number | null;
  default_unit?: string | null;
  default_meal_id?: number | null;
  is_favorite?: boolean | null;
}

export async function updateUserFood(id: number, data: UpdateFoodPayload): Promise<UserFood> {
  return apiRequest<UserFood>(`/profile/foods/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteUserFood(id: number): Promise<void> {
  const token = localStorage.getItem('token');
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const resp = await fetch(`/profile/foods/${id}`, { method: 'DELETE', headers });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: 'Delete failed' }));
    throw new Error(err.detail || `HTTP ${resp.status}`);
  }
}
