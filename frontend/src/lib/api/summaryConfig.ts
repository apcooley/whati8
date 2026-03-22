import { apiRequest } from './client';

export interface SummaryItem {
  id: number;
  nutrient_id: number | null;
  display_name: string;
  display_unit: string;
  display_order: number;
  formula: string | null;
}

export interface AvailableNutrient {
  nutrient_id: number;
  name: string;
  friendly_name: string;
  unit: string;
}

export async function getSummaryConfig(): Promise<SummaryItem[]> {
  return apiRequest<SummaryItem[]>('/summary-config');
}

export async function addSummaryItem(data: {
  nutrient_id?: number | null;
  display_name: string;
  display_unit?: string;
  formula?: string | null;
}): Promise<SummaryItem> {
  return apiRequest<SummaryItem>('/summary-config', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateSummaryItem(
  id: number,
  data: { display_name?: string; display_unit?: string; formula?: string | null }
): Promise<SummaryItem> {
  return apiRequest<SummaryItem>(`/summary-config/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteSummaryItem(id: number): Promise<void> {
  const token = localStorage.getItem('token');
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const resp = await fetch(`/summary-config/${id}`, { method: 'DELETE', headers });
  if (!resp.ok) throw new Error('Failed to delete');
}

export async function reorderSummary(itemIds: number[]): Promise<SummaryItem[]> {
  return apiRequest<SummaryItem[]>('/summary-config/reorder', {
    method: 'PUT',
    body: JSON.stringify({ item_ids: itemIds }),
  });
}

export async function getAvailableNutrients(): Promise<AvailableNutrient[]> {
  return apiRequest<AvailableNutrient[]>('/summary-config/available-nutrients');
}
