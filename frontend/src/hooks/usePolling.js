import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Polls a status URL for background task completion.
 *
 * Modeled after two patterns in the codebase:
 *   - company-dashboard.js pollTaskStatus(): 2s interval, 5 network fail limit
 *   - ai-research-assistant.js startPolling(): 2s interval, 60 max polls (2min)
 *
 * Completion states detected: SUCCESS, COMPLETED, FAILURE, FAILED
 *
 * @param {string|null} statusUrl - URL to poll (null = don't start)
 * @param {object} options
 * @param {number}   options.interval  - Poll interval in ms (default: 2000)
 * @param {number}   options.maxPolls  - Max poll attempts before timeout (default: 60)
 * @param {number}   options.maxFails  - Consecutive network failures before stop (default: 5)
 * @param {boolean}  options.enabled   - Whether polling is active (default: false)
 * @param {Function} options.onComplete - Called with data on SUCCESS/COMPLETED
 * @param {Function} options.onFail     - Called with data on FAILURE/FAILED or timeout
 *
 * @returns {{ status, data, error, isPolling, stop }}
 */
export function usePolling(statusUrl, options = {}) {
  const {
    interval = 2000,
    maxPolls = 60,
    maxFails = 5,
    enabled = false,
    onComplete,
    onFail,
  } = options;

  const [status, setStatus] = useState(null);     // last known state string
  const [data, setData] = useState(null);          // last response body
  const [error, setError] = useState(null);        // error message if failed
  const [isPolling, setIsPolling] = useState(false);

  const intervalRef = useRef(null);
  const pollCountRef = useRef(0);
  const failCountRef = useRef(0);

  // Stable callback refs
  const onCompleteRef = useRef(onComplete);
  const onFailRef = useRef(onFail);
  onCompleteRef.current = onComplete;
  onFailRef.current = onFail;

  const stop = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setIsPolling(false);
  }, []);

  useEffect(() => {
    if (!enabled || !statusUrl) {
      stop();
      return;
    }

    // Reset counters on new poll session
    pollCountRef.current = 0;
    failCountRef.current = 0;
    setStatus(null);
    setData(null);
    setError(null);
    setIsPolling(true);

    intervalRef.current = setInterval(async () => {
      pollCountRef.current++;

      if (pollCountRef.current > maxPolls) {
        stop();
        const msg = 'Polling timeout — task is taking longer than expected';
        setError(msg);
        onFailRef.current?.({ error: msg });
        return;
      }

      try {
        const response = await fetch(statusUrl);
        const result = await response.json();
        failCountRef.current = 0; // reset on successful network call
        setData(result);
        setStatus(result.state);

        const state = (result.state || '').toUpperCase();

        if (state === 'SUCCESS' || state === 'COMPLETED') {
          stop();
          onCompleteRef.current?.(result);
        } else if (state === 'FAILURE' || state === 'FAILED') {
          stop();
          const msg = result.status_message || result.error || 'Task failed';
          setError(msg);
          onFailRef.current?.(result);
        }
        // PENDING / RUNNING — continue polling
      } catch (err) {
        failCountRef.current++;
        if (failCountRef.current >= maxFails) {
          stop();
          const msg = 'Cannot check status. Task may continue in background.';
          setError(msg);
          onFailRef.current?.({ error: msg });
        }
      }
    }, interval);

    return () => stop();
  }, [statusUrl, enabled, interval, maxPolls, maxFails, stop]);

  return { status, data, error, isPolling, stop };
}
