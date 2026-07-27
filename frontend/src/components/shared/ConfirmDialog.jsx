import { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';

/**
 * ConfirmDialog — Bootstrap-styled modal replacing bare `confirm()` calls.
 *
 * Can be used as a controlled component or via the `useConfirm` hook.
 *
 * Controlled usage:
 *   <ConfirmDialog
 *     open={showConfirm}
 *     title="Delete note?"
 *     message="This action cannot be undone."
 *     confirmLabel="Delete"
 *     confirmVariant="danger"
 *     onConfirm={() => { ... }}
 *     onCancel={() => setShowConfirm(false)}
 *   />
 *
 * Hook usage:
 *   const { confirm, ConfirmDialogPortal } = useConfirm();
 *   const yes = await confirm({ title: 'Delete?', message: '...' });
 *   // Render <ConfirmDialogPortal /> somewhere in your JSX
 */
export function ConfirmDialog({
  open,
  title = 'Confirm',
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  confirmVariant = 'primary',
  onConfirm,
  onCancel,
}) {
  const dialogRef = useRef(null);

  // Focus the confirm button when dialog opens
  useEffect(() => {
    if (open && dialogRef.current) {
      const btn = dialogRef.current.querySelector('.btn-confirm-action');
      if (btn) btn.focus();
    }
  }, [open]);

  // Escape key
  useEffect(() => {
    if (!open) return;
    function handleKey(e) {
      if (e.key === 'Escape') onCancel();
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [open, onCancel]);

  if (!open) return null;

  return createPortal(
    <>
      {/* Backdrop */}
      <div
        className="modal-backdrop show"
        style={{ zIndex: 1055 }}
        onClick={onCancel}
      />
      {/* Dialog */}
      <div
        ref={dialogRef}
        className="modal d-block"
        tabIndex={-1}
        style={{ zIndex: 1056 }}
        onClick={onCancel}
      >
        <div className="modal-dialog modal-sm modal-dialog-centered" onClick={(e) => e.stopPropagation()}>
          <div className="modal-content">
            <div className="modal-header py-2">
              <h6 className="modal-title">{title}</h6>
              <button type="button" className="btn-close btn-close-sm" onClick={onCancel} />
            </div>
            {message && (
              <div className="modal-body py-2">
                <p className="mb-0 small">{message}</p>
              </div>
            )}
            <div className="modal-footer py-2">
              <button type="button" className="btn btn-sm btn-outline-secondary" onClick={onCancel}>
                {cancelLabel}
              </button>
              <button
                type="button"
                className={`btn btn-sm btn-${confirmVariant} btn-confirm-action`}
                onClick={onConfirm}
              >
                {confirmLabel}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>,
    document.body,
  );
}

/**
 * useConfirm — async confirm() replacement.
 *
 *   const { confirm, ConfirmDialogPortal } = useConfirm();
 *   const yes = await confirm({ title: 'Delete?', message: '...' });
 *   if (yes) { ... }
 */
export function useConfirm() {
  const [state, setState] = useState(null);
  const resolveRef = useRef(null);

  const confirm = useCallback((opts = {}) => {
    return new Promise((resolve) => {
      resolveRef.current = resolve;
      setState(opts);
    });
  }, []);

  const handleConfirm = useCallback(() => {
    if (resolveRef.current) resolveRef.current(true);
    setState(null);
  }, []);

  const handleCancel = useCallback(() => {
    if (resolveRef.current) resolveRef.current(false);
    setState(null);
  }, []);

  function ConfirmDialogPortal() {
    if (!state) return null;
    return (
      <ConfirmDialog
        open
        title={state.title}
        message={state.message}
        confirmLabel={state.confirmLabel}
        cancelLabel={state.cancelLabel}
        confirmVariant={state.confirmVariant}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    );
  }

  return { confirm, ConfirmDialogPortal };
}
