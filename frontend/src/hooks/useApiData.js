import { useState, useEffect, useCallback, useRef } from 'react';
import { apiFetch } from '../lib/api';

/**
 * Fetch JSON from a URL on mount (or when URL changes).
 *
 * Handles loading/error states, cleanup via AbortController on unmount
 * or when the URL changes before the request completes, and an imperative
 * `refetch()` for manual reloads.
 *
 * For React Query-managed fetches, prefer `useQuery` from @tanstack/react-query
 * instead. This hook is for simple one-off fetches where React Query setup
 * isn't warranted.
 *
 * @param {string|null} url - The URL to fetch. Pass null/undefined to skip.
 * @param {object} options
 * @param {boolean} options.enabled - Whether to fetch (default: true). Useful for conditional fetches.
 * @param {function} options.transform - Transform function applied to the response data.
 * @param {*} options.initialData - Initial value for data before fetch completes.
 * @returns {{ data, loading, error, refetch }}
 */
export function useApiData(url, options = {}) {
  const { enabled = true, transform, initialData = null } = options;

  const [data, setData] = useState(initialData);
  const [loading, setLoading] = useState(!!url && enabled);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);

  const fetchData = useCallback(
    async (signal) => {
      if (!url || !enabled) return;

      setLoading(true);
      setError(null);

      try {
        const result = await apiFetch(url, { signal });
        if (signal?.aborted) return;
        setData(transform ? transform(result) : result);
      } catch (err) {
        if (err.name === 'AbortError') return;
        setError(err);
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [url, enabled, transform],
  );

  useEffect(() => {
    if (!url || !enabled) {
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;
    fetchData(controller.signal);

    return () => {
      controller.abort();
    };
  }, [fetchData, url, enabled]);

  const refetch = useCallback(() => {
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    fetchData(controller.signal);
  }, [fetchData]);

  return { data, loading, error, refetch };
}
