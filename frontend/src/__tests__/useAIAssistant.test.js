import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

const apiPost = vi.fn();
const apiGet = vi.fn();
vi.mock('../lib/api', () => ({
  apiPost: (...a) => apiPost(...a),
  apiGet: (...a) => apiGet(...a),
}));

const { useAIAssistant } = await import('../hooks/useAIAssistant');

const ANSWER = 'Copart is asset-light because it runs on consignment.';

function setAnswer(text) {
  document.body.innerHTML = `<div id="answerEditor">${text}</div>`;
}

const savedFactcheck = {
  responses: {
    factcheck: {
      mode: 'factcheck',
      response: 'the saved fact-check',
      feedback_id: 7,
      user_answer: ANSWER,
    },
  },
};

describe('useAIAssistant saved responses', () => {
  beforeEach(() => {
    apiPost.mockReset();
    apiGet.mockReset();
    setAnswer(ANSWER);
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('serves a saved response without spending tokens when the answer is unchanged', async () => {
    apiGet.mockResolvedValue(savedFactcheck);
    const { result } = renderHook(() => useAIAssistant());

    await act(async () => { await result.current.loadHistory(1, 2); });
    await act(async () => {
      await result.current.triggerMode('factcheck', { contextRef: { current: {} } });
    });

    expect(apiPost).not.toHaveBeenCalled();
    expect(result.current.status).toBe('completed');
    expect(result.current.response).toBe('the saved fact-check');
    expect(result.current.feedbackId).toBe(7);
  });

  it('marks a reused answer, with when it was generated', async () => {
    // An instant stored answer is otherwise indistinguishable from a fast fresh
    // run, which misrepresents how current the analysis is.
    apiGet.mockResolvedValue({
      responses: {
        factcheck: {
          mode: 'factcheck',
          response: 'the saved fact-check',
          feedback_id: 7,
          user_answer: ANSWER,
          created_at: '2026-08-20T09:00:00',
        },
      },
    });
    const { result } = renderHook(() => useAIAssistant());

    await act(async () => { await result.current.loadHistory(1, 2); });
    await act(async () => {
      await result.current.triggerMode('factcheck', { contextRef: { current: {} } });
    });

    expect(result.current.reused).toBe(true);
    expect(result.current.reusedAt).toBe('2026-08-20T09:00:00');
  });

  it('does not mark a freshly generated answer as reused', async () => {
    apiGet.mockResolvedValue({ responses: {} });
    apiPost.mockResolvedValue({ success: true, task_id: 'task-9' });
    const { result } = renderHook(() => useAIAssistant());

    await act(async () => { await result.current.loadHistory(1, 2); });
    await act(async () => {
      await result.current.triggerMode('factcheck', { contextRef: { current: {} } });
    });

    expect(result.current.reused).toBe(false);
  });

  it('ignores whitespace-only differences in the answer', async () => {
    apiGet.mockResolvedValue(savedFactcheck);
    const { result } = renderHook(() => useAIAssistant());

    await act(async () => { await result.current.loadHistory(1, 2); });
    setAnswer(`  ${ANSWER.replace(/ /g, '   ')}  `);
    await act(async () => {
      await result.current.triggerMode('factcheck', { contextRef: { current: {} } });
    });

    expect(apiPost).not.toHaveBeenCalled();
    expect(result.current.response).toBe('the saved fact-check');
  });

  it('generates a fresh analysis once the answer content changes', async () => {
    apiGet.mockResolvedValue(savedFactcheck);
    apiPost.mockResolvedValue({ success: true, task_id: 'task-1' });
    const { result } = renderHook(() => useAIAssistant());

    await act(async () => { await result.current.loadHistory(1, 2); });
    setAnswer('Actually Copart owns 90% of its acreage, which is asset-heavy.');
    await act(async () => {
      await result.current.triggerMode('factcheck', { contextRef: { current: {} } });
    });

    expect(apiPost).toHaveBeenCalledTimes(1);
    expect(result.current.status).toBe('loading');
  });

  it('does not serve one mode’s response for another mode', async () => {
    apiGet.mockResolvedValue(savedFactcheck);
    apiPost.mockResolvedValue({ success: true, task_id: 'task-2' });
    const { result } = renderHook(() => useAIAssistant());

    await act(async () => { await result.current.loadHistory(1, 2); });
    await act(async () => {
      await result.current.triggerMode('elaboration', { contextRef: { current: {} } });
    });

    expect(apiPost).toHaveBeenCalledTimes(1);
    expect(result.current.response).not.toBe('the saved fact-check');
  });

  it('drops the cache on reset so another item cannot inherit it', async () => {
    apiGet.mockResolvedValue(savedFactcheck);
    apiPost.mockResolvedValue({ success: true, task_id: 'task-3' });
    const { result } = renderHook(() => useAIAssistant());

    await act(async () => { await result.current.loadHistory(1, 2); });
    act(() => { result.current.resetState(); });
    await act(async () => {
      await result.current.triggerMode('factcheck', { contextRef: { current: {} } });
    });

    expect(apiPost).toHaveBeenCalledTimes(1);
  });

  it('survives a history endpoint failure', async () => {
    apiGet.mockRejectedValue(new Error('boom'));
    apiPost.mockResolvedValue({ success: true, task_id: 'task-4' });
    const { result } = renderHook(() => useAIAssistant());

    await act(async () => { await result.current.loadHistory(1, 2); });
    await act(async () => {
      await result.current.triggerMode('factcheck', { contextRef: { current: {} } });
    });

    expect(apiPost).toHaveBeenCalledTimes(1);
  });
});
