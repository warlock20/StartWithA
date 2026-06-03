import { useState, useEffect, useRef, useMemo } from 'react';
import { createPortal } from 'react-dom';

/**
 * KillChecklistModal — Bootstrap modal for the kill-checklist workflow.
 *
 * Shows criteria (pass/fail radio buttons), a description textarea for
 * "easy kill", and a result banner. Confirms either Kill or Inbox.
 */
export function KillChecklistModal({ target, criteria, onConfirmKill, onConfirmInbox, onClose }) {
  const [answers, setAnswers] = useState({});
  const [description, setDescription] = useState('');
  const modalRef = useRef(null);
  const bsModalRef = useRef(null);

  // Open Bootstrap modal on mount
  useEffect(() => {
    if (!modalRef.current || !window.bootstrap) return;
    const modal = new window.bootstrap.Modal(modalRef.current);
    bsModalRef.current = modal;
    modal.show();

    const el = modalRef.current;
    function handleHidden() {
      onClose();
    }
    el.addEventListener('hidden.bs.modal', handleHidden);
    return () => {
      el.removeEventListener('hidden.bs.modal', handleHidden);
      modal.hide();
    };
  }, [onClose]);

  function handleRadio(criterionId, value) {
    setAnswers((prev) => ({ ...prev, [criterionId]: value }));
  }

  const failCount = useMemo(
    () => Object.values(answers).filter((v) => v === 'fail').length,
    [answers],
  );
  const answeredCount = Object.keys(answers).length;
  const allAnswered = criteria.length > 0 && answeredCount >= criteria.length;
  const hasFail = failCount > 0;

  // Determine which button to show
  const showKill = description.trim() || hasFail;
  const showInbox = !description.trim() && !hasFail && allAnswered;

  function handleConfirmKill() {
    if (description.trim()) {
      onConfirmKill({
        kill_mode: 'easy',
        kill_reason_text: description.trim(),
        notes: description.trim(),
      });
    } else {
      const killReasons = buildKillReasons();
      onConfirmKill({
        kill_reasons: killReasons,
        notes: failCount + ' of ' + criteria.length + ' criteria failed',
      });
    }
    bsModalRef.current?.hide();
  }

  function handleConfirmInbox() {
    const killReasons = buildKillReasons();
    onConfirmInbox({
      kill_reasons: killReasons,
      notes: 'All ' + criteria.length + ' kill criteria passed',
      idea_status: 'survived',
    });
    bsModalRef.current?.hide();
  }

  function buildKillReasons() {
    return criteria.map((c) => ({
      criterion_id: c.id,
      question: c.question,
      result: answers[c.id] || null,
    })).filter((r) => r.result);
  }

  const hasCriteria = criteria.length > 0;

  return createPortal(
    <div className="modal fade" ref={modalRef} tabIndex={-1} aria-hidden="true">
      <div className="modal-dialog modal-dialog-centered modal-lg">
        <div className="modal-content">
          <div className="modal-header">
            <h5 className="modal-title font-poppins">
              <i className="bi bi-shield-x text-danger" /> Kill Checklist &mdash;{' '}
              <span>{target.name}</span>
            </h5>
            <button type="button" className="btn-close" data-bs-dismiss="modal" aria-label="Close" />
          </div>
          <div className="modal-body">
            {/* Criteria list */}
            {hasCriteria && (
              <div>
                {criteria.map((c, idx) => (
                  <div key={c.id} className="sweep-kill-criterion" data-criterion-id={c.id}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', flex: 1, gap: 'var(--space-sm)' }}>
                      <span className="sweep-kill-number">{idx + 1}</span>
                      <span className="sweep-kill-question">{c.question}</span>
                    </div>
                    <div className="sweep-kill-options">
                      <label className="sweep-kill-option sweep-kill-pass">
                        <input
                          type="radio"
                          name={`kill_${c.id}`}
                          value="pass"
                          checked={answers[c.id] === 'pass'}
                          onChange={() => handleRadio(c.id, 'pass')}
                        />{' '}
                        Pass
                      </label>
                      <label className="sweep-kill-option sweep-kill-fail">
                        <input
                          type="radio"
                          name={`kill_${c.id}`}
                          value="fail"
                          checked={answers[c.id] === 'fail'}
                          onChange={() => handleRadio(c.id, 'fail')}
                        />{' '}
                        Fail
                      </label>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Description section */}
            <div>
              {hasCriteria && <hr className="my-3" />}
              <label className="form-label fw-semibold">
                <i className="bi bi-lightning-charge text-danger" />{' '}
                {hasCriteria ? 'Or describe your reason to kill' : 'Why are you killing this?'}
              </label>
              <textarea
                className="form-control"
                rows={3}
                placeholder="e.g. Promoter stake keeps dropping, auditor just resigned..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
              <small className="text-muted d-block mt-1">
                <i className="bi bi-info-circle" /> This feeds Argos so it can warn you about
                similar ideas in the future.
              </small>
            </div>
          </div>

          {/* Result banner */}
          {hasFail && !description.trim() && (
            <div className="mx-3 mt-2">
              <div className="alert alert-danger mb-0" style={{ fontSize: '0.875rem' }}>
                <i className="bi bi-x-circle" /> {failCount} criteria failed &mdash; kill this
                company.
              </div>
            </div>
          )}
          {showInbox && (
            <div className="mx-3 mt-2">
              <div className="alert alert-success mb-0" style={{ fontSize: '0.875rem' }}>
                <i className="bi bi-check-circle" /> All criteria passed &mdash; this company looks
                interesting!
              </div>
            </div>
          )}

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" data-bs-dismiss="modal">
              Cancel
            </button>
            {showKill && (
              <button type="button" className="btn btn-danger" onClick={handleConfirmKill}>
                <i className="bi bi-x-circle" /> Kill It
              </button>
            )}
            {showInbox && (
              <button type="button" className="btn btn-success" onClick={handleConfirmInbox}>
                <i className="bi bi-inbox" /> Send to Inbox
              </button>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
