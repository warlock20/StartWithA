/**
 * Shared API Client for React Islands
 *
 * Thin fetch wrapper with consistent JSON handling, error normalization,
 * and header management. Used as the fetcher layer for React Query
 * and for direct mutation calls (POST/PUT/DELETE).
 *
 * Flask APIs return: { success: bool, message?: string, error?: string, data?: any }
 */

// ---------------------------------------------------------------------------
// Custom error class
// ---------------------------------------------------------------------------
export class ApiError extends Error {
  constructor(status, message, data = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

// ---------------------------------------------------------------------------
// Core fetch wrapper
// ---------------------------------------------------------------------------
export async function apiFetch(url, options = {}) {
  const { body, headers: customHeaders, ...rest } = options;

  const headers = { ...customHeaders };
  let processedBody = body;

  if (body instanceof FormData) {
    // FormData — let browser set Content-Type (multipart boundary).
    // Flask checks this header to detect AJAX requests.
    headers['X-Requested-With'] = 'XMLHttpRequest';
    processedBody = body;
  } else if (body != null && typeof body === 'object') {
    headers['Content-Type'] = 'application/json';
    processedBody = JSON.stringify(body);
  }

  const response = await fetch(url, { ...rest, headers, body: processedBody });

  // Parse JSON (or return null for 204 No Content)
  let data = null;
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    data = await response.json();
  } else if (response.status !== 204) {
    const text = await response.text();
    data = { message: text };
  }

  if (!response.ok) {
    const message = (data && (data.error || data.message)) || response.statusText;
    throw new ApiError(response.status, message, data);
  }

  return data;
}

// ---------------------------------------------------------------------------
// Convenience methods — used as React Query fetchers and for mutations
// ---------------------------------------------------------------------------
export function apiGet(url) {
  return apiFetch(url, { method: 'GET' });
}

export function apiPost(url, body) {
  return apiFetch(url, { method: 'POST', body });
}

export function apiPut(url, body) {
  return apiFetch(url, { method: 'PUT', body });
}

export function apiDelete(url) {
  return apiFetch(url, { method: 'DELETE' });
}
