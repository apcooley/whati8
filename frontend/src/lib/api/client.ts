import { get } from 'svelte/store';
import { authStore } from '../stores/auth';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Get the user's local timezone string.
 * Returns IANA timezone identifier (e.g., 'America/Denver')
 */
export function getUserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    return 'UTC'; // Fallback to UTC if detection fails
  }
}

/**
 * Add timezone query parameter to URL.
 * If URL already has query params, appends with &
 */
function addTimezoneToUrl(url: string, timezone: string): string {
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}user_timezone=${encodeURIComponent(timezone)}`;
}

const API_BASE = '/api/v1';

export async function apiRequest<T>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const { token } = get(authStore);
  const timezone = getUserTimezone();

  // Prepend versioned base path
  const versionedUrl = `${API_BASE}${url}`;

  // Add timezone to URL for GET requests
  // For POST/PUT, timezone can be in request body or query param
  const urlWithTimezone = addTimezoneToUrl(versionedUrl, timezone);

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    'X-User-Timezone': timezone, // Also send as header for convenience
    ...options.headers,
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(urlWithTimezone, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
    let message: string;
    if (typeof errorData.detail === 'string') {
      message = errorData.detail;
    } else if (Array.isArray(errorData.detail)) {
      message = errorData.detail.map((e: any) => e.msg || JSON.stringify(e)).join('; ');
    } else {
      message = `HTTP ${response.status}`;
    }
    throw new ApiError(response.status, message);
  }

  // 204 No Content has no body
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}
