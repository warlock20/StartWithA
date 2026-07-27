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
 * @returns {object} AI assistant state and actions
 */
export function useAIAssistant({
  apiEndpoint = '/research/workflow/ai_assist',
  statusEndpoint = '/research/workflow/ai_assist/status',
  feedbackEndpoint = '/research/workflow/ai_assist/feedback',
  regenerateEndpoint = '/research/workflow/ai_assist/regenerate',
} = {}) {
  const [mode, setMode] = useState(null);
  const [status, setStatus] = useState('idle');       // idle | loading | completed | failed | tokenLimit
  const [response, setResponse] = useState(null);
  const [feedbackId, setFeedbackId] = useState(null);
  const [error, setError] = useState(null);
  const [tokenLimitData, setTokenLimitData] = useState(null);

  // Track the polling URL and whether polling is active
  const [pollUrl, setPollUrl] = useState(null);
  const [pollEnabled, setPollEnabled] = useState(false);

  // Keep mode in a ref so polling callbacks see the latest value
  const modeRef = useRef(null);

  // ── Polling via shared hook ──
  const { stop: stopPolling } = usePolling(pollUrl, {
    enabled: pollEnabled,
    maxPolls: 60,
    maxFails: 5,
    onComplete: useCallback((result) => {
      setPollEnabled(false);
      setStatus('completed');
      setResponse(
        modeRef.current === 'runprompt' ? result.ai_suggestion : result.response,
      );
      setFeedbackId(result.feedback_id || null);
      if (result.tokens_used) {
        console.log(`AI ${modeRef.current} success: ${result.tokens_used} tokens used`);
      }
    }, []),
    onFail: useCallback((result) => {
      setPollEnabled(false);
      setStatus('failed');
      setError(result?.error || result?.status_message || 'Analysis failed');
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
  }, []);

  // ── Start polling for a task ──
  function startTaskPolling(taskId, m, endpoint) {
    modeRef.current = m;
    setPollUrl(`${endpoint}/${taskId}`);
    setPollEnabled(true);
  }

  // ── Trigger a standard AI mode (challenge / elaboration / factcheck) ──
  async function triggerMode(m, { contextRef, useWebSearch } = {}) {
    const answerText = getAnswerText();
    if (!answerText || answerText.trim().length < 10) {
      alert('Please write something in your answer before using AI assistance.');
      return false;
    }

    if (typeof window.checkAIConsent === 'function') {
      const consented = await window.checkAIConsent();
      if (!consented) return false;
    }

    const ctx = contextRef?.current || {};
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
        startTaskPolling(resp.task_id, m, statusEndpoint);
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

    setStatus('loading');
    setResponse(null);

    try {
      const resp = await apiPost(regenerateEndpoint, {
        feedback_id: feedbackId,
        use_google_search: useWebSearch,
      });

      if (resp.success && resp.task_id) {
        startTaskPolling(resp.task_id, mode, statusEndpoint);
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

    // Actions
    triggerMode,
    runPrompt,
    regenerate,
    dismiss,
    resetState,
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
