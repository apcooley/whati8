import { get } from 'svelte/store';
import { authStore } from '../stores/auth';

export interface RecognizedItem {
  name: string;
  serving_description: string;
  serving_size_g: number;
  confidence: string;
  nutrients: Record<string, number>;
}

export interface RecognitionResult {
  is_nutrition_label: boolean;
  items: RecognizedItem[];
}

export async function recognizePhoto(file: File): Promise<RecognitionResult> {
  const { token } = get(authStore);
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch('/photo/recognize', {
    method: 'POST',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: formData,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Recognition failed' }));
    throw new Error(err.detail || `HTTP ${response.status}`);
  }

  return response.json();
}
