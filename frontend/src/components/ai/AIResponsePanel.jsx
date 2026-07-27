import { useState } from 'react';
import { apiPost } from '../../lib/api';
import { formatAIResponse } from '../../lib/formatAIResponse';

const MODE_CONFIG = {
  challenge: { icon: 'bi-exclamation-diamond', color: 'danger', title: 'Challenge' },
  elaboration: { icon: 'bi-chat-dots', color: 'primary', title: 'Elaboration' },
  factcheck: { icon: 'bi-shield-exclamation', color: 'warning', title: 'Fact-Check' },
  runprompt: { icon: 'bi-play-circle', color: 'info', title: 'AI Analysis' },
};

/**
 * AI response display panel with feedback buttons.
 * Renders the formatted response in a Bootstrap alert with mode-specific styling.
 */
export function AIResponsePanel({
  mode,
  responseText,
  feedbackId,
  onRegenerate,
  onDismiss,
  feedbackEndpoint,
}) {
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(null);
  const [copyLabel, setCopyLabel] = useState('Copy');

  const config = MODE_CONFIG[mode] || MODE_CONFIG.challenge;
  const formattedHtml = formatAIResponse(responseText);

  async function handleFeedback(value) {
    if (!feedbackId) return;
    setFeedbackSubmitted(value);
    try {
      await apiPost(feedbackEndpoint, { feedback_id: feedbackId, feedback: value });
    } catch (err) {
      console.error('Feedback error:', err);
      setFeedbackSubmitted(null);
    }
  }

  function handleCopy() {
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = formattedHtml;
    const textContent = tempDiv.textContent || tempDiv.innerText || '';

    navigator.clipboard
      .writeText(textContent)
      .then(() => {
        setCopyLabel('Copied!');
        setTimeout(() => setCopyLabel('Copy'), 2000);
      })
      .catch((err) => {
        console.error('Copy failed:', err);
        alert('Failed to copy. Please select and copy manually.');
      });
  }

  return (
    <div className="ai-response-content" style={{ display: 'block' }}>
      <div className={`alert alert-${config.color} border-start border-${config.color} border-4`}>
        <div className="d-flex align-items-center mb-2">
          <i className={`bi ${config.icon} me-2`} style={{ fontSize: '1.2rem' }} />
          <strong>{config.title}</strong>
        </div>
        {/* eslint-disable-next-line react/no-danger */}
        <div dangerouslySetInnerHTML={{ __html: formattedHtml }} />
      </div>

      {/* Feedback buttons */}
      <div className="ai-feedback-buttons">
        <div className="d-flex flex-wrap gap-2 justify-content-between align-items-center mt-3 pt-2 border-top">
          <div className="d-flex gap-2">
            <button
              type="button"
              className={`btn btn-sm ${
                feedbackSubmitted === 'helpful' ? 'btn-success' : 'btn-outline-success'
              }`}
              onClick={() => handleFeedback('helpful')}
              disabled={!!feedbackSubmitted}
            >
              <i className="bi bi-hand-thumbs-up me-1" /> Helpful
            </button>
            <button
              type="button"
              className={`btn btn-sm ${
                feedbackSubmitted === 'not_helpful' ? 'btn-danger' : 'btn-outline-danger'
              }`}
              onClick={() => handleFeedback('not_helpful')}
              disabled={!!feedbackSubmitted}
            >
              <i className="bi bi-hand-thumbs-down me-1" /> Not Helpful
            </button>
          </div>
          <div className="d-flex gap-2">
            {onRegenerate && (
              <button
                type="button"
                className="btn btn-sm btn-outline-primary"
                onClick={onRegenerate}
              >
                <i className="bi bi-arrow-clockwise me-1" /> Regenerate
              </button>
            )}
            <button
              type="button"
              className={`btn btn-sm ${
                copyLabel === 'Copied!' ? 'btn-success' : 'btn-outline-secondary'
              }`}
              onClick={handleCopy}
            >
              <i className={`bi ${copyLabel === 'Copied!' ? 'bi-check' : 'bi-clipboard'} me-1`} />{' '}
              {copyLabel}
            </button>
            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={onDismiss}>
              <i className="bi bi-x-lg me-1" /> Dismiss
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
