import { useRef, useEffect, useCallback } from 'react';

const AI_MODES = [
  { key: 'challenge', icon: 'exclamation-triangle', title: 'Challenge', btnClass: 'challenge' },
  { key: 'elaboration', icon: 'question-circle', title: 'Follow-Up Questions', btnClass: 'elaborate' },
  { key: 'factcheck', icon: 'shield-check', title: 'Fact-Check', btnClass: 'factcheck' },
];

/**
 * QuestionCard — expandable card for a single research question.
 *
 * When expanded, lazily initialises a BlockNote editor and renders the
 * AI Research Tools toolbar. The toolbar DOM IDs (`aiResponse-{id}`,
 * `aiUseWebSearch-{id}`) match what `AIResearchAssistant.triggerForQuestion`
 * expects, so the vanilla AI assistant can manipulate them directly.
 */
export function QuestionCard({
  question,
  isExpanded,
  onToggleExpand,
  onToggleStatus,
  onDelete,
  onSaveAnswer,
  companyName,
}) {
  const editorInitRef = useRef(false);
  const isAnswered = question.status === 'answered';
  const statusLabel = isAnswered ? 'Answered' : 'Exploring';
  const statusIcon = isAnswered ? 'check-circle-fill' : 'search';
  const editorId = 'standalone-editor-' + question.id;

  // Initialise BlockNote editor on first expand
  useEffect(() => {
    if (!isExpanded || editorInitRef.current) return;

    var tryInit = setInterval(function () {
      var container = document.getElementById(editorId);
      if (container && window.initBlockNoteEditor) {
        clearInterval(tryInit);
        editorInitRef.current = true;
        window.initBlockNoteEditor(editorId, {
          initialContent: question.answer_content || '',
          placeholder: 'Write your research findings here...',
          onChange: function (json) {
            onSaveAnswer(question.id, json);
          },
        });
      }
    }, 100);

    return () => clearInterval(tryInit);
  }, [isExpanded]); // eslint-disable-line react-hooks/exhaustive-deps

  const triggerAI = useCallback(
    (mode) => {
      var container = document.getElementById(editorId);
      var answerText = container ? container.textContent || container.innerText || '' : '';

      if (window.AIResearchAssistant && window.AIResearchAssistant.triggerForQuestion) {
        window.AIResearchAssistant.triggerForQuestion(question.id, mode, {
          answerText: answerText,
          questionText: question.question_text,
          companyName: companyName,
          showToast: window.showToast || function () {},
        });
      }
    },
    [question.id, question.question_text, companyName, editorId],
  );

  return (
    <div className="research-summary-card" style={{ marginBottom: '0.75rem' }}>
      <div className="research-summary-header" onClick={() => onToggleExpand(question.id)}>
        <div className="research-summary-header-left">
          <i className="bi bi-question-circle-fill" style={{ color: 'var(--accent-color)' }} />
          <span className="research-step-name">{question.question_text}</span>
          <span className={'research-qa-status ' + question.status}>{statusLabel}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button
            className="action-btn"
            style={{ padding: '2px 8px', fontSize: '0.75rem' }}
            onClick={(e) => {
              e.stopPropagation();
              onToggleStatus(question.id);
            }}
            title="Toggle status"
          >
            <i className={'bi bi-' + statusIcon} />
          </button>
          <button
            className="action-btn"
            style={{ padding: '2px 8px', fontSize: '0.75rem', color: 'var(--danger-500)' }}
            onClick={(e) => {
              e.stopPropagation();
              onDelete(question.id);
            }}
            title="Delete"
          >
            <i className="bi bi-trash" />
          </button>
          <i className="bi bi-chevron-down" style={{ color: 'var(--gray-400)' }} />
        </div>
      </div>

      <div className={'research-summary-body' + (isExpanded ? '' : ' collapsed')}>
        <div id={editorId} style={{ minHeight: 120 }} />

        {/* AI Research Tools — DOM IDs match AIResearchAssistant expectations */}
        <div className="fr-ai-assistant">
          <h6>
            <i className="bi bi-robot me-1" /> AI Research Tools
          </h6>
          <div className="fr-ai-mode-buttons">
            {AI_MODES.map((m) => (
              <button
                key={m.key}
                className={'fr-ai-mode-btn ' + m.btnClass}
                onClick={() => triggerAI(m.key)}
              >
                <i className={'bi bi-' + m.icon} /> {m.title}
              </button>
            ))}
          </div>
          <div className="ai-search-toggle">
            <label className="ai-search-toggle-label">
              <input
                type="checkbox"
                id={'aiUseWebSearch-' + question.id}
                className="form-check-input ai-web-search-checkbox"
              />
              <i className="bi bi-globe2" />
              <span>Use web search</span>
              <small className="text-muted">(uses more credits)</small>
            </label>
          </div>
          <div className="fr-ai-response" id={'aiResponse-' + question.id} />
        </div>
      </div>
    </div>
  );
}
