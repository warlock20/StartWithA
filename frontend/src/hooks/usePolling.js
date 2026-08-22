import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Polls a status URL for background task completion.
 *
 * Modeled after two patterns in the codebase:
 *   - company-dashboard.js pollTaskStatus(): 2s interval, 5 network fail limit
 *   - ai-research-assistant.js startPolling(): 2s interval, 60 max polls (2min)
 *
 * Completion states detected: SUCCESS, COMPLETED, FAILURE, FAILED, NOT_FOUND.
 *
 * NOT_FOUND is terminal: the status endpoints return it with a 404 and a JSON
 * body, so treating it as "keep waiting" burned the whole poll budget on a task
 * that could never arrive.
 *
 * When the budget runs out we make one final reconciliation request before
 * declaring failure. Background tasks here have been observed finishing at 272s
 * — well past any client budget — and without this check that finished result
 * was discarded even though it was sitting in the database.
 *
 * @param {string|null} statusUrl - URL to poll (null = don't start)
 * @param {object} options
 * @param {number}   options.interval  - Poll interval in ms (default: 2000)
 * @param {number}   options.maxPolls  - Max poll attempts before timeout (default: 60)
 * @param {number}   options.maxFails  - Consecutive network failures before stop (default: 5)
 * @param {boolean}  options.enabled   - Whether polling is active (default: false)
 * @param {Function} options.onComplete - Called with data on SUCCESS/COMPLETED
 * @param {Function} options.onFail     - Called with data on FAILURE/FAILED, NOT_FOUND or timeout
 *
 * @returns {{ status, data, error, isPolling, stop }}
 */

const SUCCESS_STATES = ['SUCCESS', 'COMPLETED'];
const FAILURE_STATES = ['FAILURE', 'FAILED'];
const MISSING_STATES = ['NOT_FOUND'];

const MISSING_MESSAGE =
  'This analysis is no longer available. Please run it again.';

/**
 * Turn the last known task state into something the user can act on.
 * PENDING and RUNNING mean genuinely different things: PENDING at timeout
 * means no worker ever picked the task up, RUNNING means the model is slow.
 */
function timeoutMessage(lastState) {
  if (lastState === 'PENDING') {
    return 'The analysis never started — the background worker may not be running. '
      + 'Nothing was processed, so no credits were used.';
  }
  if (lastState === 'RUNNING') {
    return 'Still running — this is taking longer than expected. '
      + 'The result is saved when it finishes, so you can check again in a moment.';
  }
  return 'Polling timeout — task is taking longer than expected';
}

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
  const lastStateRef = useRef(null);

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
    lastStateRef.current = null;
    setStatus(null);
    setData(null);
    setError(null);
    setIsPolling(true);

    const succeed = (result) => {
      setData(result);
      setStatus(result.state);
      onCompleteRef.current?.(result);
    };

    const fail = (message, result) => {
      setError(message);
      onFailRef.current?.({
        ...result,
        error: message,
        lastState: lastStateRef.current,
      });
    };

    /**
     * Budget exhausted. Make one last request so a task that finished between
     * the final poll and now is still delivered rather than thrown away.
     */
    const reconcile = async () => {
      try {
        const response = await fetch(statusUrl);
        const result = await response.json();
        const state = (result.state || '').toUpperCase();
        lastStateRef.current = state || lastStateRef.current;
        setData(result);
        setStatus(result.state);

        if (SUCCESS_STATES.includes(state)) {
          succeed(result);
          return;
        }
        if (FAILURE_STATES.includes(state)) {
          fail(result.status_message || result.error || 'Task failed', result);
          return;
        }
        if (MISSING_STATES.includes(state)) {
          fail(MISSING_MESSAGE, result);
          return;
        }
        fail(timeoutMessage(lastStateRef.current), result);
      } catch {
        fail(timeoutMessage(lastStateRef.current), {});
      }
    };

    intervalRef.current = setInterval(async () => {
      pollCountRef.current++;

      if (pollCountRef.current > maxPolls) {
        stop();
        await reconcile();
        return;
      }

      try {
        const response = await fetch(statusUrl);
        const result = await response.json();
        failCountRef.current = 0; // reset on successful network call
        setData(result);
        setStatus(result.state);

        const state = (result.state || '').toUpperCase();
        lastStateRef.current = state || lastStateRef.current;

        if (SUCCESS_STATES.includes(state)) {
          stop();
          succeed(result);
        } else if (FAILURE_STATES.includes(state)) {
          stop();
          fail(result.status_message || result.error || 'Task failed', result);
        } else if (MISSING_STATES.includes(state)) {
          // Terminal: the task row is gone, waiting cannot help.
          stop();
          fail(MISSING_MESSAGE, result);
        }
        // PENDING / RUNNING — continue polling
      } catch {
        failCountRef.current++;
        if (failCountRef.current >= maxFails) {
          stop();
          fail('Cannot check status. Task may continue in background.', {});
        }
      }
    }, interval);

    return () => stop();
  }, [statusUrl, enabled, interval, maxPolls, maxFails, stop]);

  return { status, data, error, isPolling, stop };
}
