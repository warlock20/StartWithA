import { useState, useRef, useCallback } from 'react';
import { apiPost, apiGet } from '../lib/api';
import { usePolling } from './usePolling';

/**
 * Encapsulates AI assistant state: mode selection, task submission,
 * background polling (via usePolling), and response handling.
 *
 * @param {object} opts
 * @param {string} opts.apiEndpoint       - POST endpoint to trigger AI analysis
 * @param {string} opts.statusEndpoint    - GET endpoint prefix for polling (appended with /{taskId})
 * @param {string} opts.feedbackEndpoint  - POST endpoint for feedback
 * @param {string} opts.regenerateEndpoint - POST endpoint for regeneration
 * @param {string} opts.historyEndpoint    - GET endpoint prefix for saved responses
 *                                           (appended with /{analysisId}/{itemId})
 * @returns {object} AI assistant state and actions
 */
const POLL_INTERVAL_MS = 2000;

// Mirrors Config.AI_ASSIST_SOFT_TIME_LIMIT. The server value is handed down via
// the page config; this is only the fallback for callers that don't pass one.
export const DEFAULT_AI_ASSIST_TIMEOUT_SECONDS = 420;

// Analyses without web search finish far sooner, and spending the whole server
// budget before reporting a task that never started helps nobody.
const FAST_PATH_FRACTION = 0.5;

/**
 * Convert the server's time limit into a poll count.
 *
 * The budget is derived rather than hardcoded so the browser and the Celery
 * soft limit always give up at the same point: if the client quits first, a
 * finished answer is stranded in the database; if the worker quits first, the
 * user waits on a task that is already dead. A flat 60-poll (120s) budget was
 * the original bug — real runs have taken 272s.
 */
function budgetFromTimeout(timeoutSeconds, fraction = 1) {
  return Math.max(1, Math.ceil((timeoutSeconds * 1000 * fraction) / POLL_INTERVAL_MS));
}

// Whitespace-insensitive so that re-serialising the editor's blocks (which can
// shuffle newlines without changing a word) does not read as an edit.
const normalizeAnswer = (s) => (s || '').replace(/\s+/g, ' ').trim();

/** Whether a saved response was generated from the answer now in the editor. */
function sameAnswer(stored, current) {
  const a = normalizeAnswer(stored);
  return a.length > 0 && a === normalizeAnswer(current);
}

export function useAIAssistant({
  apiEndpoint = '/research/workflow/ai_assist',
  statusEndpoint = '/research/workflow/ai_assist/status',
  feedbackEndpoint = '/research/workflow/ai_assist/feedback',
  regenerateEndpoint = '/research/workflow/ai_assist/regenerate',
  historyEndpoint = '/research/workflow/ai_assist/history',
  timeoutSeconds = DEFAULT_AI_ASSIST_TIMEOUT_SECONDS,
} = {}) {
  const fastPathBudget = budgetFromTimeout(timeoutSeconds, FAST_PATH_FRACTION);
  const [mode, setMode] = useState(null);
  const [status, setStatus] = useState('idle');       // idle | loading | completed | failed | tokenLimit
  const [response, setResponse] = useState(null);
  const [feedbackId, setFeedbackId] = useState(null);
  const [error, setError] = useState(null);
  const [tokenLimitData, setTokenLimitData] = useState(null);

  // Track the polling URL and whether polling is active
  const [pollUrl, setPollUrl] = useState(null);
  const [pollEnabled, setPollEnabled] = useState(false);
  const [pollBudget, setPollBudget] = useState(fastPathBudget);
  // A timeout is worth retrying; a provider error (429/503) is not — re-polling
  // would just re-read the same terminal failure.
  const [recoverable, setRecoverable] = useState(false);

  // Keep mode in a ref so polling callbacks see the latest value
  const modeRef = useRef(null);

  // Saved responses for the open checklist item, keyed by mode. A ref rather
  // than state: reading it must never re-render, and it is always consulted
  // inside an event handler.
  const historyRef = useRef({});
  // The answer text a generation was launched from, so a completed response can
  // be cached against the content it actually describes.
  const pendingAnswerRef = useRef(null);

  // ── Polling via shared hook ──
  const { stop: stopPolling } = usePolling(pollUrl, {
    enabled: pollEnabled,
    interval: POLL_INTERVAL_MS,
    maxPolls: pollBudget,
    maxFails: 5,
    onComplete: useCallback((result) => {
      setPollEnabled(false);
      setStatus('completed');
      const text = modeRef.current === 'runprompt' ? result.ai_suggestion : result.response;
      setResponse(text);
      setFeedbackId(result.feedback_id || null);
      // Cache against the answer it was generated from, so switching modes and
      // back is instant and costs nothing.
      if (modeRef.current && pendingAnswerRef.current !== null) {
        historyRef.current[modeRef.current] = {
          mode: modeRef.current,
          response: text,
          feedback_id: result.feedback_id || null,
          user_answer: pendingAnswerRef.current,
        };
      }
      if (result.tokens_used) {
        console.log(`AI ${modeRef.current} success: ${result.tokens_used} tokens used`);
      }
    }, []),
    onFail: useCallback((result) => {
      setPollEnabled(false);
      setStatus('failed');
      setError(result?.error || result?.status_message || 'Analysis failed');
      // We only ran out of patience if the task was still pending or running.
      setRecoverable(['PENDING', 'RUNNING'].includes(result?.lastState));
    }, []),
  });

  // ── Reset ──
  const resetState = useCallback(() => {
    setMode(null);
    modeRef.current = null;
    setStatus('idle');
    setResponse(null);
    setFeedbackId(null);
    setError(null);
    setTokenLimitData(null);
    setPollEnabled(false);
    setPollUrl(null);
    setPollBudget(fastPathBudget);
    setRecoverable(false);
    historyRef.current = {};
    pendingAnswerRef.current = null;
  }, [fastPathBudget]);

  // ── Start polling for a task ──
  function startTaskPolling(taskId, m, endpoint, { useWebSearch = false } = {}) {
    modeRef.current = m;
    setPollBudget(budgetFromTimeout(timeoutSeconds, useWebSearch ? 1 : FAST_PATH_FRACTION));
    setRecoverable(false);
    setPollUrl(`${endpoint}/${taskId}`);
    setPollEnabled(true);
  }

  // ── Re-check a task the client gave up on ──
  // The task keeps running server-side after the client stops polling, so a
  // timeout is recoverable: resume polling against the same task rather than
  // making the user re-run (and re-pay for) an analysis that may already exist.
  const checkAgain = useCallback(() => {
    if (!pollUrl) return;
    setStatus('loading');
    setError(null);
    setRecoverable(false);
    setPollEnabled(true);
  }, [pollUrl]);

  // ── Load previously saved responses for this checklist item ──
  // Every response is persisted to ai_research_feedback, so switching modes or
  // leaving the item no longer has to discard it.
  const loadHistory = useCallback(async (analysisId, itemId) => {
    if (!analysisId || !itemId) return;
    try {
      const result = await apiGet(`${historyEndpoint}/${analysisId}/${itemId}`);
      historyRef.current = result?.responses || {};
    } catch {
      // A missing history is not worth surfacing — the user can still generate.
      historyRef.current = {};
    }
  }, [historyEndpoint]);

  // ── Trigger a standard AI mode (challenge / elaboration / factcheck) ──
  async function triggerMode(m, { contextRef, useWebSearch } = {}) {
    const answerText = getAnswerText();
    if (!answerText || answerText.trim().length < 10) {
      alert('Please write something in your answer before using AI assistance.');
      return false;
    }

    // A saved response generated from this exact answer is still valid, so show
    // it instead of paying to regenerate an identical analysis. Editing the
    // answer changes the content and falls through to a fresh run; the
    // Regenerate button remains the manual override.
    const cached = historyRef.current[m];
    if (cached && sameAnswer(cached.user_answer, answerText)) {
      stopPolling();
      setMode(m);
      modeRef.current = m;
      setResponse(cached.response);
      setFeedbackId(cached.feedback_id || null);
      setError(null);
      setTokenLimitData(null);
      setRecoverable(false);
      setStatus('completed');
      return true;
    }

    if (typeof window.checkAIConsent === 'function') {
      const consented = await window.checkAIConsent();
      if (!consented) return false;
    }

    const ctx = contextRef?.current || {};
    pendingAnswerRef.current = answerText;
    setMode(m);
    modeRef.current = m;
    setStatus('loading');
    setResponse(null);
    setFeedbackId(null);
    setError(null);
    setTokenLimitData(null);

    try {
      const resp = await apiPost(apiEndpoint, {
        mode: m,
        question_text: ctx.question_text,
        answer_text: answerText,
        analysis_id: ctx.analysis_id,
        item_id: ctx.item_id,
        company_name: ctx.company_name,
        use_google_search: useWebSearch,
      });

      if (resp.success && resp.task_id) {
        startTaskPolling(resp.task_id, m, statusEndpoint, { useWebSearch });
      } else {
        setStatus('failed');
        setError(resp.error || 'Unknown error occurred');
      }
    } catch (err) {
      if (err.status === 429) {
        setStatus('tokenLimit');
        setTokenLimitData(err.data || {});
      } else {
        setStatus('failed');
        setError('Network error. Please check your connection and try again.');
        console.error('AI assist error:', err);
      }
    }

    return true;
  }

  // ── Run Prompt (checklist-specific) ──
  async function runPrompt({ analysisId, itemId }) {
    setMode('runprompt');
    modeRef.current = 'runprompt';
    setStatus('loading');
    setResponse(null);
    setFeedbackId(null);
    setError(null);
    setTokenLimitData(null);

    try {
      const resp = await apiPost(
        `/research/workflow/checklist/${analysisId}/item/${itemId}/ai_analyze`,
        { selected_document_ids: [] },
      );

      if (resp.success && resp.task_id) {
        startTaskPolling(resp.task_id, 'runprompt', '/research/workflow/checklist/ai_analyze/status');
      } else {
        setStatus('failed');
        setError(resp.message || 'Failed to start analysis.');
      }
    } catch (err) {
      setStatus('failed');
      setError('Network error. Please try again.');
      console.error('Run Prompt error:', err);
    }
  }

  // ── Regenerate ──
  async function regenerate({ useWebSearch } = {}) {
    if (!feedbackId) return;

    // Deliberate refresh: drop the saved copy so the new answer replaces it
    // rather than being shadowed by the old one on the next mode switch.
    if (mode) delete historyRef.current[mode];
    pendingAnswerRef.current = getAnswerText();
    setStatus('loading');
    setResponse(null);

    try {
      const resp = await apiPost(regenerateEndpoint, {
        feedback_id: feedbackId,
        use_google_search: useWebSearch,
      });

      if (resp.success && resp.task_id) {
        startTaskPolling(resp.task_id, mode, statusEndpoint, { useWebSearch });
      } else {
        setStatus('failed');
        setError(resp.error || 'Regeneration failed');
      }
    } catch (err) {
      if (err.status === 429) {
        setStatus('tokenLimit');
        setTokenLimitData(err.data || {});
      } else {
        setStatus('failed');
        setError('Network error. Please try again.');
        console.error('Regeneration error:', err);
      }
    }
  }

  // ── Dismiss ──
  function dismiss() {
    stopPolling();
    // Dismissal is excluded from the history endpoint; keeping it locally would
    // resurrect it until the next reload.
    if (mode) delete historyRef.current[mode];
    if (feedbackId) {
      apiPost(feedbackEndpoint, { feedback_id: feedbackId, feedback: 'dismissed' }).catch(() => {});
    }
    resetState();
  }

  return {
    // State
    mode,
    status,
    response,
    feedbackId,
    error,
    tokenLimitData,
    canCheckAgain: !!pollUrl && recoverable,

    // Actions
    triggerMode,
    runPrompt,
    regenerate,
    dismiss,
    resetState,
    checkAgain,
    loadHistory,
  };
}

// ── Bridge helper: read answer text from BlockNote / textarea on the page ──
function getAnswerText() {
  const editorContainer = document.getElementById('answerEditor');
  if (editorContainer) {
    return editorContainer.textContent || editorContainer.innerText || '';
  }
  const fallback = document.getElementById('answer_text');
  if (fallback && fallback.value) {
    try {
      const blocks = JSON.parse(fallback.value);
      let text = '';
      blocks.forEach((block) => {
        if (block.content && Array.isArray(block.content)) {
          block.content.forEach((item) => {
            if (item.type === 'text' && item.text) text += item.text + ' ';
          });
          text += '\n';
        }
      });
      return text.trim();
    } catch {
      return fallback.value.trim();
    }
  }
  return '';
}
