import { useState, useEffect, useRef, useCallback } from 'react';
import { apiPost, apiGet } from '../../lib/api';
import { formatAIResponse } from '../../lib/formatAIResponse';
import { AIResponsePanel } from './AIResponsePanel';

const MODE_LOADING = {
  challenge: 'Analyzing your reasoning and preparing counter-arguments...',
  elaboration: 'Crafting follow-up questions to deepen your analysis...',
  factcheck: 'Identifying claims that need verification...',
  factcheck_search: 'Searching the web and verifying claims...',
  runprompt: 'Running checklist prompt analysis...',
};

/**
 * AI Research Assistant — React island for the research step page.
 *
 * Renders the collapsible AI tools panel with mode buttons (Challenge, Elaboration,
 * Fact-Check, Run Prompt), web search toggle, and response area.
 *
 * Bridge pattern: reads answer text from #answerEditor (BlockNote) or #answer_text
 * (fallback textarea) on the same page.
 *
 * Exposes `window.aiAssistant` with:
 *   - updateContext(data)  — called during AJAX navigation to update item context
 *   - triggerMode(mode)    — programmatic trigger (backward compat)
 *   - formatResponse(text) — shared text formatter (backward compat)
 *   - context              — current context object (backward compat)
 *
 * Props (via config):
 *   context: { analysis_id, item_id, company_name, question_text }
 *   hasLlmPrompt: boolean
 *   analysisId: number
 *   apiEndpoint, statusEndpoint, feedbackEndpoint, regenerateEndpoint
 */
export function AIAssistant({ config }) {
  const [expanded, setExpanded] = useState(false);
  const [mode, setMode] = useState(null);
  const [status, setStatus] = useState('idle');
  const [response, setResponse] = useState(null);
  const [feedbackId, setFeedbackId] = useState(null);
  const [useWebSearch, setUseWebSearch] = useState(false);
  const [tokenLimitData, setTokenLimitData] = useState(null);
  const [error, setError] = useState(null);
  const [hasLlmPrompt, setHasLlmPrompt] = useState(config.hasLlmPrompt);

  const contextRef = useRef(config.context);
  const pollRef = useRef(null);

  const apiEndpoint = config.apiEndpoint || '/research/workflow/ai_assist';
  const statusEndpoint = config.statusEndpoint || '/research/workflow/ai_assist/status';
  const feedbackEndpoint = config.feedbackEndpoint || '/research/workflow/ai_assist/feedback';
  const regenerateEndpoint = config.regenerateEndpoint || '/research/workflow/ai_assist/regenerate';

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------

  /** Read answer text from the editor (bridge pattern). */
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

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  const resetState = useCallback(() => {
    setMode(null);
    setStatus('idle');
    setResponse(null);
    setFeedbackId(null);
    setError(null);
    setTokenLimitData(null);
    stopPolling();
  }, []);

  // ------------------------------------------------------------------
  // Expose global API
  // ------------------------------------------------------------------
  useEffect(() => {
    window.aiAssistant = {
      updateContext: (data) => {
        contextRef.current = {
          ...contextRef.current,
          item_id: data.item_id,
          question_text: data.text,
        };
        setHasLlmPrompt(!!data.has_llm_prompt);
        resetState();
        setExpanded(false);
      },
      triggerMode: (m) => handleTriggerMode(m),
      formatResponse: formatAIResponse,
      get context() {
        return contextRef.current;
      },
    };
    return () => {
      delete window.aiAssistant;
    };
  }, [resetState]);

  // Cleanup polling on unmount
  useEffect(() => () => stopPolling(), []);

  // ------------------------------------------------------------------
  // GDPR consent
  // ------------------------------------------------------------------
  async function checkConsent() {
    if (typeof window.checkAIConsent === 'function') {
      return await window.checkAIConsent();
    }
    return true;
  }

  // ------------------------------------------------------------------
  // Polling
  // ------------------------------------------------------------------
  function startPolling(taskId, pollMode, pollEndpoint) {
    stopPolling();
    let pollCount = 0;
    const maxPolls = 60; // 2-min timeout

    pollRef.current = setInterval(async () => {
      pollCount++;
      if (pollCount > maxPolls) {
        stopPolling();
        setStatus('failed');
        setError('AI analysis is taking longer than expected. Please try again.');
        return;
      }

      try {
        const data = await apiGet(`${pollEndpoint}/${taskId}`);

        if (data.state === 'COMPLETED') {
          stopPolling();
          setStatus('completed');
          setResponse(pollMode === 'runprompt' ? data.ai_suggestion : data.response);
          setFeedbackId(data.feedback_id || null);
          if (data.tokens_used) {
            console.log(`AI ${pollMode} success: ${data.tokens_used} tokens used`);
          }
        } else if (data.state === 'FAILED') {
          stopPolling();
          setStatus('failed');
          setError(data.error || 'Analysis failed');
        }
        // PENDING / RUNNING — continue
      } catch (err) {
        console.error('Poll error:', err);
        // Keep retrying on transient errors
      }
    }, 2000);
  }

  // ------------------------------------------------------------------
  // Trigger AI mode (challenge / elaboration / factcheck)
  // ------------------------------------------------------------------
  async function handleTriggerMode(m) {
    setExpanded(true);

    const answerText = getAnswerText();
    if (!answerText || answerText.trim().length < 10) {
      alert('Please write something in your answer before using AI assistance.');
      return;
    }

    const consented = await checkConsent();
    if (!consented) return;

    setMode(m);
    setStatus('loading');
    setResponse(null);
    setFeedbackId(null);
    setError(null);
    setTokenLimitData(null);

    try {
      const resp = await apiPost(apiEndpoint, {
        mode: m,
        question_text: contextRef.current.question_text,
        answer_text: answerText,
        analysis_id: contextRef.current.analysis_id,
        item_id: contextRef.current.item_id,
        company_name: contextRef.current.company_name,
        use_google_search: useWebSearch,
      });

      if (resp.success && resp.task_id) {
        startPolling(resp.task_id, m, statusEndpoint);
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
  }

  // ------------------------------------------------------------------
  // Run Prompt (separate endpoint for checklist-specific prompts)
  // ------------------------------------------------------------------
  async function handleRunPrompt() {
    setExpanded(true);
    setMode('runprompt');
    setStatus('loading');
    setResponse(null);
    setFeedbackId(null);
    setError(null);
    setTokenLimitData(null);

    const analysisId = config.analysisId;
    const itemId = contextRef.current.item_id;

    try {
      const resp = await apiPost(
        `/research/workflow/checklist/${analysisId}/item/${itemId}/ai_analyze`,
        { selected_document_ids: [] },
      );

      if (resp.success && resp.task_id) {
        startPolling(resp.task_id, 'runprompt', '/research/workflow/checklist/ai_analyze/status');
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

  // ------------------------------------------------------------------
  // Regenerate
  // ------------------------------------------------------------------
  async function handleRegenerate() {
    if (!feedbackId) return;

    setStatus('loading');
    setResponse(null);

    try {
      const resp = await apiPost(regenerateEndpoint, {
        feedback_id: feedbackId,
        use_google_search: useWebSearch,
      });

      if (resp.success && resp.task_id) {
        startPolling(resp.task_id, mode, statusEndpoint);
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

  // ------------------------------------------------------------------
  // Dismiss
  // ------------------------------------------------------------------
  function handleDismiss() {
    stopPolling();
    if (feedbackId) {
      apiPost(feedbackEndpoint, { feedback_id: feedbackId, feedback: 'dismissed' }).catch(() => {});
    }
    resetState();
  }

  // ------------------------------------------------------------------
  // Render helpers
  // ------------------------------------------------------------------
  function getLoadingMessage() {
    if (mode === 'factcheck' && useWebSearch) return MODE_LOADING.factcheck_search;
    return MODE_LOADING[mode] || 'AI is analyzing...';
  }

  function renderTokenLimitError() {
    let resetDateText = 'unknown date';
    if (tokenLimitData?.reset_date) {
      const resetDate = new Date(tokenLimitData.reset_date);
      resetDateText = resetDate.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    }

    return (
      <div className="alert alert-warning" role="alert">
        <div className="d-flex align-items-start">
          <i className="bi bi-exclamation-triangle-fill me-3 fs-4" />
          <div className="flex-grow-1">
            <h6 className="alert-heading mb-2">
              <strong>AI Token Limit Reached</strong>
            </h6>
            <p className="mb-2">
              You&rsquo;ve used{' '}
              <strong>{tokenLimitData?.tokens_used?.toLocaleString() || 'all'}</strong> of your{' '}
              <strong>{tokenLimitData?.tokens_limit?.toLocaleString() || 'monthly'}</strong> AI
              tokens.
            </p>
            <p className="mb-2 small">
              Your token limit will reset on <strong>{resetDateText}</strong>.
            </p>
            <hr className="my-2" />
            <p className="mb-0 small">
              <a href="/settings/profile/" className="alert-link">
                <i className="bi bi-graph-up me-1" />
                View your token usage and subscription details
              </a>
            </p>
          </div>
        </div>
      </div>
    );
  }

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------
  return (
    <div className={`cl-ai-tools${expanded ? ' expanded' : ''}`} id="aiToolsPanel">
      <div className="cl-ai-tools-header" onClick={() => setExpanded(!expanded)}>
        <h6>
          <i className="bi bi-robot" /> AI Research Assistant
        </h6>
        <i className="bi bi-chevron-down" />
      </div>
      <div className="cl-ai-tools-body">
        {/* Mode Buttons */}
        <div className="cl-ai-mode-buttons">
          <button
            type="button"
            className="cl-ai-mode-btn challenge"
            onClick={() => handleTriggerMode('challenge')}
            disabled={status === 'loading'}
          >
            <i className="bi bi-exclamation-triangle" /> Challenge
          </button>
          <button
            type="button"
            className="cl-ai-mode-btn elaborate"
            onClick={() => handleTriggerMode('elaboration')}
            disabled={status === 'loading'}
          >
            <i className="bi bi-question-circle" /> Elaboration
          </button>
          <button
            type="button"
            className="cl-ai-mode-btn factcheck"
            onClick={() => handleTriggerMode('factcheck')}
            disabled={status === 'loading'}
          >
            <i className="bi bi-shield-check" /> Fact-Check
          </button>
          {hasLlmPrompt && (
            <button
              type="button"
              className="cl-ai-mode-btn run-prompt"
              id="btnRunPrompt"
              onClick={handleRunPrompt}
              disabled={status === 'loading'}
              title="Run the predefined AI prompt for this checklist item"
            >
              <i
                className={`bi ${
                  status === 'loading' && mode === 'runprompt'
                    ? 'bi-hourglass-split'
                    : 'bi-play-circle'
                }`}
              />{' '}
              {status === 'loading' && mode === 'runprompt' ? 'Running...' : 'Run Prompt'}
            </button>
          )}
        </div>

        {/* Web Search Toggle */}
        <div className="ai-search-toggle">
          <label className="ai-search-toggle-label">
            <input
              type="checkbox"
              id="aiUseWebSearch"
              className="form-check-input"
              checked={useWebSearch}
              onChange={(e) => setUseWebSearch(e.target.checked)}
            />
            <i className="bi bi-globe2" />
            <span>Use web search</span>
            <small className="text-muted">(uses more credits)</small>
          </label>
        </div>

        {/* Response Area */}
        {status !== 'idle' && (
          <div id="aiResponseArea" style={{ display: 'block' }}>
            {/* Loading */}
            {status === 'loading' && (
              <div id="aiLoadingSpinner" className="text-center py-4">
                <div className="spinner-border text-primary" role="status">
                  <span className="visually-hidden">Loading...</span>
                </div>
                <p className="mt-2 text-muted">{getLoadingMessage()}</p>
              </div>
            )}

            {/* Token Limit */}
            {status === 'tokenLimit' && renderTokenLimitError()}

            {/* Error */}
            {status === 'failed' && error && (
              <div className="alert alert-danger">
                <i className="bi bi-exclamation-circle me-2" />
                {error}
              </div>
            )}

            {/* Completed Response */}
            {status === 'completed' && response && (
              <AIResponsePanel
                mode={mode}
                responseText={response}
                feedbackId={feedbackId}
                onRegenerate={mode !== 'runprompt' ? handleRegenerate : null}
                onDismiss={handleDismiss}
                feedbackEndpoint={feedbackEndpoint}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
