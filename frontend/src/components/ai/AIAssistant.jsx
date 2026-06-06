import { useState, useEffect, useRef } from 'react';
import { formatAIResponse } from '../../lib/formatAIResponse';
import { useAIAssistant } from '../../hooks/useAIAssistant';
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
  const [useWebSearch, setUseWebSearch] = useState(false);
  const [hasLlmPrompt, setHasLlmPrompt] = useState(config.hasLlmPrompt);

  const contextRef = useRef(config.context);

  const ai = useAIAssistant({
    apiEndpoint: config.apiEndpoint,
    statusEndpoint: config.statusEndpoint,
    feedbackEndpoint: config.feedbackEndpoint,
    regenerateEndpoint: config.regenerateEndpoint,
  });

  const feedbackEndpoint =
    config.feedbackEndpoint || '/research/workflow/ai_assist/feedback';

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
        ai.resetState();
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
  }, [ai.resetState]);

  // ------------------------------------------------------------------
  // Mode trigger
  // ------------------------------------------------------------------
  async function handleTriggerMode(m) {
    setExpanded(true);
    await ai.triggerMode(m, { contextRef, useWebSearch });
  }

  // ------------------------------------------------------------------
  // Run Prompt
  // ------------------------------------------------------------------
  async function handleRunPrompt() {
    setExpanded(true);
    await ai.runPrompt({
      analysisId: config.analysisId,
      itemId: contextRef.current.item_id,
    });
  }

  // ------------------------------------------------------------------
  // Regenerate
  // ------------------------------------------------------------------
  async function handleRegenerate() {
    await ai.regenerate({ useWebSearch });
  }

  // ------------------------------------------------------------------
  // Render helpers
  // ------------------------------------------------------------------
  function getLoadingMessage() {
    if (ai.mode === 'factcheck' && useWebSearch) return MODE_LOADING.factcheck_search;
    return MODE_LOADING[ai.mode] || 'AI is analyzing...';
  }

  function renderTokenLimitError() {
    let resetDateText = 'unknown date';
    if (ai.tokenLimitData?.reset_date) {
      const resetDate = new Date(ai.tokenLimitData.reset_date);
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
              <strong>{ai.tokenLimitData?.tokens_used?.toLocaleString() || 'all'}</strong> of your{' '}
              <strong>{ai.tokenLimitData?.tokens_limit?.toLocaleString() || 'monthly'}</strong> AI
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
            disabled={ai.status === 'loading'}
          >
            <i className="bi bi-exclamation-triangle" /> Challenge
          </button>
          <button
            type="button"
            className="cl-ai-mode-btn elaborate"
            onClick={() => handleTriggerMode('elaboration')}
            disabled={ai.status === 'loading'}
          >
            <i className="bi bi-question-circle" /> Elaboration
          </button>
          <button
            type="button"
            className="cl-ai-mode-btn factcheck"
            onClick={() => handleTriggerMode('factcheck')}
            disabled={ai.status === 'loading'}
          >
            <i className="bi bi-shield-check" /> Fact-Check
          </button>
          {hasLlmPrompt && (
            <button
              type="button"
              className="cl-ai-mode-btn run-prompt"
              id="btnRunPrompt"
              onClick={handleRunPrompt}
              disabled={ai.status === 'loading'}
              title="Run the predefined AI prompt for this checklist item"
            >
              <i
                className={`bi ${
                  ai.status === 'loading' && ai.mode === 'runprompt'
                    ? 'bi-hourglass-split'
                    : 'bi-play-circle'
                }`}
              />{' '}
              {ai.status === 'loading' && ai.mode === 'runprompt' ? 'Running...' : 'Run Prompt'}
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
        {ai.status !== 'idle' && (
          <div id="aiResponseArea" style={{ display: 'block' }}>
            {/* Loading */}
            {ai.status === 'loading' && (
              <div id="aiLoadingSpinner" className="text-center py-4">
                <div className="spinner-border text-primary" role="status">
                  <span className="visually-hidden">Loading...</span>
                </div>
                <p className="mt-2 text-muted">{getLoadingMessage()}</p>
              </div>
            )}

            {/* Token Limit */}
            {ai.status === 'tokenLimit' && renderTokenLimitError()}

            {/* Error */}
            {ai.status === 'failed' && ai.error && (
              <div className="alert alert-danger">
                <i className="bi bi-exclamation-circle me-2" />
                {ai.error}
              </div>
            )}

            {/* Completed Response */}
            {ai.status === 'completed' && ai.response && (
              <AIResponsePanel
                mode={ai.mode}
                responseText={ai.response}
                feedbackId={ai.feedbackId}
                onRegenerate={ai.mode !== 'runprompt' ? handleRegenerate : null}
                onDismiss={ai.dismiss}
                feedbackEndpoint={feedbackEndpoint}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
