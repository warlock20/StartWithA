import { useEffect, useRef } from 'react';

/**
 * useBootstrapModal — creates the Bootstrap modal once on mount and shows it.
 *
 * `onClose` is held in a ref so a parent passing a fresh inline function on
 * every render does not re-create the modal. Without window.bootstrap (e.g.
 * jsdom) the effect is a no-op.
 *
 * Returns { modalRef, bsModalRef, hide }. Attach modalRef to the .modal element.
 * `onShown` (optional) runs on shown.bs.modal; it is also read through a ref.
 */
export function useBootstrapModal(onClose, onShown) {
  const modalRef = useRef(null);
  const bsModalRef = useRef(null);
  const onCloseRef = useRef(onClose);
  const onShownRef = useRef(onShown);
  onCloseRef.current = onClose;
  onShownRef.current = onShown;

  useEffect(() => {
    const el = modalRef.current;
    if (!el || !window.bootstrap) return undefined;
    const modal = new window.bootstrap.Modal(el);
    bsModalRef.current = modal;

    function handleShown() {
      if (onShownRef.current) onShownRef.current();
    }
    function handleHidden() {
      onCloseRef.current();
    }
    el.addEventListener('shown.bs.modal', handleShown);
    el.addEventListener('hidden.bs.modal', handleHidden);
    modal.show();
    return () => {
      el.removeEventListener('shown.bs.modal', handleShown);
      el.removeEventListener('hidden.bs.modal', handleHidden);
      modal.hide();
      bsModalRef.current = null;
    };
  }, []);

  function hide() {
    if (bsModalRef.current) bsModalRef.current.hide();
  }

  return { modalRef, bsModalRef, hide };
}
