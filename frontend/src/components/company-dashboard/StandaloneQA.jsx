import { useState, useEffect, useCallback, useRef } from 'react';
import { QuestionCard } from './QuestionCard';

/**
 * StandaloneQA — React island for the company dashboard Research > Q&A section.
 *
 * Replaces the vanilla StandaloneQA object from company-dashboard.js.
 * Manages research question CRUD, per-question BlockNote editors, status
 * toggling, and AI research tool integration (delegated to the vanilla
 * window.AIResearchAssistant).
 *
 * Props (via config):
 *   companyId   — numeric company ID for API endpoints
 *   companyName — company name for AI context and empty state text
 */
export function StandaloneQA({ companyId, companyName }) {
  const [questions, setQuestions] = useState([]);
  const [expandedId, setExpandedId] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newQuestionText, setNewQuestionText] = useState('');
  const [loading, setLoading] = useState(true);
  const inputRef = useRef(null);

  var listUrl = '/companies/api/' + companyId + '/research-questions';
  var questionUrl = '/research/workflow/api/questions/';

  // Fetch questions on mount
  useEffect(() => {
    fetch(listUrl)
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (data.success) setQuestions(data.questions);
      })
      .catch(function (err) {
        console.error('Error loading research questions:', err);
      })
      .finally(function () {
        setLoading(false);
      });
  }, [listUrl]);

  // Focus input when add form appears
  useEffect(() => {
    if (showAddForm && inputRef.current) inputRef.current.focus();
  }, [showAddForm]);

  var toggleExpand = useCallback(function (questionId) {
    setExpandedId(function (prev) {
      return prev === questionId ? null : questionId;
    });
  }, []);

  var toggleStatus = useCallback(
    function (questionId) {
      var question = questions.find(function (q) {
        return q.id === questionId;
      });
      if (!question) return;
      var newStatus = question.status === 'exploring' ? 'answered' : 'exploring';

      fetch(questionUrl + questionId, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      })
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          if (data.success) {
            setQuestions(function (prev) {
              return prev.map(function (q) {
                return q.id === questionId ? Object.assign({}, q, { status: newStatus }) : q;
              });
            });
            if (window.showToast)
              window.showToast(
                newStatus === 'answered' ? 'Marked as answered' : 'Marked as exploring',
              );
          }
        })
        .catch(function (err) {
          console.error('Error toggling status:', err);
        });
    },
    [questions, questionUrl],
  );

  var deleteQuestion = useCallback(
    function (questionId) {
      if (!confirm('Delete this research question?')) return;

      fetch(questionUrl + questionId, { method: 'DELETE' })
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          if (data.success) {
            setQuestions(function (prev) {
              return prev.filter(function (q) {
                return q.id !== questionId;
              });
            });
            if (window.showToast) window.showToast('Question deleted');
          }
        })
        .catch(function (err) {
          console.error('Error deleting question:', err);
        });
    },
    [questionUrl],
  );

  var saveAnswer = useCallback(
    function (questionId, content) {
      setQuestions(function (prev) {
        return prev.map(function (q) {
          return q.id === questionId ? Object.assign({}, q, { answer_content: content }) : q;
        });
      });

      fetch(questionUrl + questionId, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answer_content: content }),
      }).catch(function (err) {
        console.error('Error saving answer:', err);
      });
    },
    [questionUrl],
  );

  var createQuestion = useCallback(
    function () {
      var text = newQuestionText.trim();
      if (!text) return;

      fetch(listUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question_text: text }),
      })
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          if (data.success) {
            setQuestions(function (prev) {
              return prev.concat([data.question]);
            });
            setNewQuestionText('');
            setShowAddForm(false);
            if (window.showToast) window.showToast('Question added');
          } else {
            if (window.showToast)
              window.showToast(data.message || 'Error adding question', 'danger');
          }
        })
        .catch(function () {
          if (window.showToast) window.showToast('Network error', 'danger');
        });
    },
    [newQuestionText, listUrl],
  );

  var handleKeyDown = useCallback(
    function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        createQuestion();
      }
    },
    [createQuestion],
  );

  return (
    <>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '1rem',
        }}
      >
        <h5 style={{ margin: 0, fontSize: 'var(--font-size-base)', fontWeight: 600 }}>
          <i className="bi bi-chat-square-text me-1" /> Research Questions
        </h5>
        <button
          type="button"
          className="position-btn primary"
          onClick={() => setShowAddForm(true)}
        >
          <i className="bi bi-plus-circle me-1" /> Add Question
        </button>
      </div>

      {/* Add Question Form */}
      {showAddForm && (
        <div style={{ marginBottom: '1rem' }}>
          <div className="research-summary-card" style={{ padding: 'var(--space-md)' }}>
            <input
              type="text"
              className="form-control"
              ref={inputRef}
              placeholder="What do you want to research?"
              value={newQuestionText}
              onChange={(e) => setNewQuestionText(e.target.value)}
              onKeyDown={handleKeyDown}
              style={{ marginBottom: '0.5rem' }}
            />
            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
              <button
                type="button"
                className="position-btn"
                onClick={() => {
                  setShowAddForm(false);
                  setNewQuestionText('');
                }}
              >
                Cancel
              </button>
              <button type="button" className="position-btn primary" onClick={createQuestion}>
                <i className="bi bi-plus me-1" /> Add
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Questions List */}
      {questions.map(function (q) {
        return (
          <QuestionCard
            key={q.id}
            question={q}
            isExpanded={expandedId === q.id}
            onToggleExpand={toggleExpand}
            onToggleStatus={toggleStatus}
            onDelete={deleteQuestion}
            onSaveAnswer={saveAnswer}
            companyName={companyName}
          />
        );
      })}

      {/* Empty State */}
      {!loading && questions.length === 0 && (
        <div className="journey-empty-state">
          <i className="bi bi-chat-square-text" />
          <h4>No Research Questions Yet</h4>
          <p>Add questions to track what you want to research about {companyName}.</p>
        </div>
      )}
    </>
  );
}
