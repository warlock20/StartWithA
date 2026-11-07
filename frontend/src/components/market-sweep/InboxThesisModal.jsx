import { useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useBootstrapModal } from './useBootstrapModal.js';

/**
 * InboxThesisModal — small Bootstrap modal shown before a sweep row is sent
 * to the Inbox, with an optional one-sentence thesis.
 *
 * Props:
 *   target: { id, name }
 *   onConfirm: (thesis: string) => void — '' means no thesis, otherwise trimmed text
 *   onClose: () => void — dialog dismissed without promoting
 */
export function InboxThesisModal({ target, onConfirm, onClose }) {
  const [thesis, setThesis] = useState('');
  const inputRef = useRef(null);
  const { modalRef, hide } = useBootstrapModal(onClose, () => {
    if (inputRef.current) inputRef.current.focus();
  });

  function confirm(value) {
    onConfirm(value);
    hide();
  }

  function handleSubmit(e) {
    e.preventDefault();
    confirm(thesis.trim());
  }

  return createPortal(
    <div className="modal fade" ref={modalRef} tabIndex={-1} aria-hidden="true">
      <div className="modal-dialog modal-dialog-centered">
        <div className="modal-content">
          <form onSubmit={handleSubmit}>
            <div className="modal-header">
              <h5 className="modal-title font-poppins">Send to Inbox: {target.name}</h5>
              <button type="button" className="btn-close" data-bs-dismiss="modal" aria-label="Close" />
            </div>
            <div className="modal-body">
              <label className="form-label fw-semibold" htmlFor="inbox-thesis-input">
                One-sentence thesis <span className="text-muted fw-normal">(optional)</span>
              </label>
              <input
                id="inbox-thesis-input"
                ref={inputRef}
                type="text"
                className="form-control"
                autoFocus
                maxLength={500}
                placeholder="Why might this be interesting?"
                value={thesis}
                onChange={(e) => setThesis(e.target.value)}
              />
              <small className="text-muted d-block mt-1">
                Saved as the idea's thesis. You can change it later on Edit Idea.
              </small>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-link me-auto"
                onClick={() => confirm('')}
              >
                Send without thesis
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                data-bs-dismiss="modal"
                onClick={onClose}
              >
                Cancel
              </button>
              <button type="submit" className="btn btn-success">
                <i className="bi bi-inbox" /> Send to Inbox
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>,
    document.body,
  );
}
