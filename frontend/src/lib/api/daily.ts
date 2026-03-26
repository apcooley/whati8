import { apiRequest } from './client';
import type { DailyLogResponse } from '../types/profile';

export async function getDailyLogs(date: string): Promise<DailyLogResponse> {
  return apiRequest<DailyLogResponse>(`/logs/daily/${date}`);
}

export interface QuickLogPayload {
  user_food_id: number;
  quantity?: number | null;
  unit?: string | null;
  meal_id?: number | null;
  logged_at?: string | null;
}

export async function quickLog(data: QuickLogPayload) {
  return apiRequest('/logs/quick', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function deleteLog(logId: number): Promise<void> {
  await apiRequest<void>(`/logs/${logId}`, { method: 'DELETE' });
}

export async function updateLog(
  logId: number,
  data: { quantity?: number; unit?: string; meal_id?: number | null; notes?: string | null }
) {
  return apiRequest(`/logs/${logId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function copyLog(logId: number, targetDate: string, mealId?: number) {
  return apiRequest(`/logs/${logId}/copy`, {
    method: 'POST',
    body: JSON.stringify({ target_date: targetDate, meal_id: mealId }),
  });
}

export async function moveLog(logId: number, targetDate?: string, mealId?: number) {
  return apiRequest(`/logs/${logId}/move`, {
    method: 'PATCH',
    body: JSON.stringify({ target_date: targetDate, meal_id: mealId }),
  });
}

export async function copyMeal(sourceDate: string, sourceMealId: number, targetDate: string, targetMealId?: number) {
  return apiRequest('/logs/copy-meal', {
    method: 'POST',
    body: JSON.stringify({ source_date: sourceDate, source_meal_id: sourceMealId, target_date: targetDate, target_meal_id: targetMealId }),
  });
}
