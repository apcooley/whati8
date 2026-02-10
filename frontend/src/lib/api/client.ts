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

export async function apiRequest<T>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const { token } = get(authStore);
  const timezone = getUserTimezone();

  // Add timezone to URL for GET requests
  // For POST/PUT, timezone can be in request body or query param
  const urlWithTimezone = addTimezoneToUrl(url, timezone);

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
    throw new ApiError(
      response.status,
      errorData.detail || `HTTP ${response.status}`
    );
  }

  return response.json();
}
