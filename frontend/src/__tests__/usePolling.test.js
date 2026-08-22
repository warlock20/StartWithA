import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { usePolling } from '../hooks/usePolling';

/**
 * Regression tests for the "Polling timeout" bug in the checklist
 * AI Research Assistant.
 *
 * Both failure modes below were confirmed against real background_task rows:
 *   - a task left `pending` (started_at NULL) because no worker consumed it
 *   - a task that ran 272s and completed long after the client gave up
 */

const flushPolls = async (n, interval = 2000) => {
  for (let i = 0; i < n; i++) {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(interval);
    });
  }
};

const jsonResponse = (body, ok = true, status = 200) => ({
  ok,
  status,
  json: async () => body,
});

describe('usePolling', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('stops immediately when the task is NOT_FOUND instead of polling to timeout', async () => {
    global.fetch.mockResolvedValue(jsonResponse({ state: 'NOT_FOUND' }, false, 404));
    const onFail = vi.fn();

    renderHook(() => usePolling('/status/abc', { enabled: true, onFail }));
    await flushPolls(3);

    expect(onFail).toHaveBeenCalledTimes(1);
    expect(onFail.mock.calls[0][0].error).toMatch(/no longer available|not found/i);
    // Terminal on the first response — must not keep polling.
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it('recovers a result that lands after the poll budget is exhausted', async () => {
    // Mode B: task completes at ~272s, after the client budget ran out.
    global.fetch.mockResolvedValue(jsonResponse({ state: 'RUNNING' }));
    const onComplete = vi.fn();
    const onFail = vi.fn();

    renderHook(() =>
      usePolling('/status/abc', { enabled: true, maxPolls: 3, onComplete, onFail }),
    );
    await flushPolls(3);

    // Budget exhausted; the final reconciliation check finds the finished task.
    global.fetch.mockResolvedValue(
      jsonResponse({ state: 'COMPLETED', response: 'the answer' }),
    );
    await flushPolls(1);

    expect(onComplete).toHaveBeenCalled();
    expect(onComplete.mock.calls[0][0].response).toBe('the answer');
    expect(onFail).not.toHaveBeenCalled();
  });

  it('reports a never-started task distinctly from a slow one', async () => {
    // Mode A: worker never consumed the task, so it stays PENDING.
    global.fetch.mockResolvedValue(jsonResponse({ state: 'PENDING' }));
    const onFail = vi.fn();

    renderHook(() =>
      usePolling('/status/abc', { enabled: true, maxPolls: 2, onFail }),
    );
    await flushPolls(4);

    expect(onFail).toHaveBeenCalled();
    const { error, lastState } = onFail.mock.calls[0][0];
    expect(lastState).toBe('PENDING');
    expect(error).toMatch(/never started|has not started|worker/i);
  });

  it('reports a slow running task as still running', async () => {
    global.fetch.mockResolvedValue(jsonResponse({ state: 'RUNNING' }));
    const onFail = vi.fn();

    renderHook(() =>
      usePolling('/status/abc', { enabled: true, maxPolls: 2, onFail }),
    );
    await flushPolls(4);

    expect(onFail).toHaveBeenCalled();
    const { error, lastState } = onFail.mock.calls[0][0];
    expect(lastState).toBe('RUNNING');
    expect(error).toMatch(/still running|taking longer/i);
  });
});
