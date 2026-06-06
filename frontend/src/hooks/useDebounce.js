import { useState, useEffect } from 'react';

/**
 * Debounces a value by the given delay.
 *
 * Common delays in this codebase:
 *   250ms — autocomplete (send-to-sector)
 *   300ms — search inputs (company-search, journal search)
 *   500ms — duplicate detection
 *   800ms — ticker lookup
 *
 * @param {*} value - The value to debounce
 * @param {number} delay - Delay in milliseconds (default: 300)
 * @returns {*} The debounced value
 */
export function useDebounce(value, delay = 300) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}
