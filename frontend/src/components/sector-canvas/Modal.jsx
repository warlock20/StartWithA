import { useEffect } from 'react';
import { createPortal } from 'react-dom';

/**
 * Lightweight modal using Bootstrap CSS classes (no bootstrap.Modal JS).
 * Controlled entirely by React state.
 */
export function Modal({ isOpen, onClose, title, children, footer, size = '' }) {
  // Handle Escape key
  useEffect(() => {
    if (!isOpen) return;
    function handleKey(e) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', handleKey);
    document.body.classList.add('modal-open');
    return () => {
      document.removeEventListener('keydown', handleKey);
      document.body.classList.remove('modal-open');
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return createPortal(
    <>
      <div className="modal-backdrop fade show" onClick={onClose} />
      <div
        className="modal fade show"
        style={{ display: 'block' }}
        tabIndex="-1"
        onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      >
        <div className={`modal-dialog ${size}`}>
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">{title}</h5>
              <button type="button" className="btn-close" onClick={onClose} />
            </div>
            <div className="modal-body">{children}</div>
            {footer && <div className="modal-footer">{footer}</div>}
          </div>
        </div>
      </div>
    </>,
    document.body
  );
}
