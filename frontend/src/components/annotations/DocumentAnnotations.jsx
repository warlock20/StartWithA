import { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { apiGet, apiPost, apiPut, apiDelete } from '../../lib/api';
import { AnnotationPopover } from './AnnotationPopover';
import { AnnotationSidebar } from './AnnotationSidebar';

/**
 * DocumentAnnotations — React island for PDF annotation management.
 *
 * Manages pin and text-highlight annotations on PDF pages. Renders the
 * annotation sidebar list and popover editor via React Portals into the
 * existing template DOM. Pins and highlight classes are applied imperatively
 * to the PDF page wrappers via useEffect, with event delegation for clicks.
 *
 * Props:
 *   resourceId, companyId, companyName
 *
 * Backward compat:
 *   window.DocumentAnnotations = { toggleSidebar, enterAddMode }
 */
export function DocumentAnnotations({ resourceId, companyId, companyName }) {
  const [annotations, setAnnotations] = useState([]);
  const [isAddMode, setIsAddMode] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [popover, setPopover] = useState(null);
  const [highlightAction, setHighlightAction] = useState(null);

  // Refs for stable access from DOM event handlers
  const overlaysRef = useRef([]);
  const annotationsRef = useRef(annotations);
  annotationsRef.current = annotations;

  // ------------------------------------------------------------------
  // Setup: discover PDF page wrappers
  // ------------------------------------------------------------------
  useEffect(() => {
    const wrappers = document.querySelectorAll('.pdf-page-canvas-wrapper');
    overlaysRef.current = Array.from(wrappers).map((wrapper) => ({
      pageNumber: parseInt(wrapper.dataset.pageNumber),
      overlayEl: null,
      wrapperEl: wrapper,
    }));
  }, []);

  // ------------------------------------------------------------------
  // Load annotations on mount
  // ------------------------------------------------------------------
  const loadAnnotations = useCallback(async () => {
    try {
      const result = await apiGet(`/companies/api/resources/${resourceId}/annotations`);
      if (result.success) {
        setAnnotations(result.data.annotations);
      }
    } catch (err) {
      console.error('Failed to load annotations:', err);
    }
  }, [resourceId]);

  useEffect(() => {
    loadAnnotations();
  }, [loadAnnotations]);

  // ------------------------------------------------------------------
  // CRUD helpers
  // ------------------------------------------------------------------
  const createAnnotation = useCallback(
    async (payload) => {
      try {
        const result = await apiPost(
          `/companies/api/resources/${resourceId}/annotations`,
          payload,
        );
        if (result.success) {
          setAnnotations((prev) => [...prev, result.data.annotation]);
          return result.data.annotation;
        }
      } catch (err) {
        console.error('Failed to create annotation:', err);
      }
      return null;
    },
    [resourceId],
  );

  const updateAnnotationApi = useCallback(async (annotationId, content, scope) => {
    try {
      const result = await apiPut(`/companies/api/annotations/${annotationId}`, { content, scope });
      if (result.success) {
        const updated = result.data.annotation;
        setAnnotations((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
        return updated;
      }
    } catch (err) {
      console.error('Failed to update annotation:', err);
    }
    return null;
  }, []);

  const deleteAnnotationApi = useCallback(async (annotationId) => {
    try {
      const result = await apiDelete(`/companies/api/annotations/${annotationId}`);
      if (result.success) {
        setAnnotations((prev) => prev.filter((a) => a.id !== annotationId));
        return true;
      }
    } catch (err) {
      console.error('Failed to delete annotation:', err);
    }
    return false;
  }, []);

  const sendToJournalApi = useCallback(async (annotationId) => {
    try {
      return await apiPost(`/companies/api/annotations/${annotationId}/send-to-journal`);
    } catch (err) {
      console.error('Failed to send to journal:', err);
      return null;
    }
  }, []);

  // ------------------------------------------------------------------
  // Render pins & highlights into PDF wrappers (imperative DOM)
  // ------------------------------------------------------------------
  useEffect(() => {
    // Clear existing pins (keep temp "new" pins)
    overlaysRef.current.forEach((o) => {
      o.wrapperEl
        .querySelectorAll('.annotation-pin:not(.annotation-pin--new)')
        .forEach((p) => p.remove());
    });

    // Clear existing highlight classes
    document.querySelectorAll('.annotation-highlight').forEach((el) => {
      el.classList.remove('annotation-highlight');
      el.removeAttribute('data-annotation-id');
    });

    // Render each annotation
    annotations.forEach((ann) => {
      if (ann.annotation_type === 'highlight') {
        applyHighlightToDOM(ann);
      } else {
        const entry = overlaysRef.current.find((o) => o.pageNumber === ann.page_number);
        if (entry && ann.x_percent != null && ann.y_percent != null) {
          const pin = document.createElement('div');
          pin.className = 'annotation-pin';
          pin.dataset.annotationId = ann.id;
          pin.style.left = ann.x_percent + '%';
          pin.style.top = ann.y_percent + '%';
          pin.title = truncate(ann.content, 60);
          entry.wrapperEl.appendChild(pin);
        }
      }
    });
  }, [annotations]);

  function applyHighlightToDOM(annotation) {
    const entry = overlaysRef.current.find((o) => o.pageNumber === annotation.page_number);
    if (!entry) return;

    const textLayer = entry.wrapperEl.querySelector('.textLayer');
    if (!textLayer || !annotation.anchor_text) return;

    // Only use leaf spans (skip markedContent wrappers)
    const allSpans = textLayer.querySelectorAll('span');
    const spans = [];
    allSpans.forEach((span) => {
      if (!span.querySelector('span')) spans.push(span);
    });

    // Build concatenated text and span index mapping
    let fullText = '';
    const spanMap = [];
    spans.forEach((span) => {
      const start = fullText.length;
      fullText += span.textContent;
      spanMap.push({ span, startIdx: start, endIdx: fullText.length });
    });

    // Find anchor text in concatenated page text
    let matchIdx = fullText.indexOf(annotation.anchor_text);
    if (matchIdx === -1) {
      const normalizedFull = fullText.replace(/\s+/g, ' ');
      const normalizedAnchor = annotation.anchor_text.replace(/\s+/g, ' ');
      matchIdx = normalizedFull.indexOf(normalizedAnchor);
    }
    if (matchIdx === -1) return;

    const matchEnd = matchIdx + annotation.anchor_text.length;

    // Mark all spans overlapping the match
    spanMap.forEach((e) => {
      if (e.endIdx > matchIdx && e.startIdx < matchEnd) {
        e.span.classList.add('annotation-highlight');
        e.span.dataset.annotationId = annotation.id;
      }
    });
  }

  // ------------------------------------------------------------------
  // Event delegation: pin & highlight clicks on page wrappers
  // ------------------------------------------------------------------
  useEffect(() => {
    function handleWrapperClick(e) {
      const viewer = document.getElementById('pdf-viewer');
      if (!viewer) return;
      const viewerRect = viewer.getBoundingClientRect();

      // Pin click
      const pin = e.target.closest('.annotation-pin:not(.annotation-pin--new)');
      if (pin) {
        e.stopPropagation();
        const annotationId = parseInt(pin.dataset.annotationId);
        const ann = annotationsRef.current.find((a) => a.id === annotationId);
        if (!ann) return;

        const anchorRect = pin.getBoundingClientRect();
        const top = anchorRect.bottom - viewerRect.top + viewer.scrollTop + 8;
        let left = anchorRect.left - viewerRect.left + viewer.scrollLeft - 10;
        if (left + 320 > viewer.clientWidth - 16) left = viewer.clientWidth - 320 - 16;
        if (left < 8) left = 8;

        pin.classList.add('active');
        setPopover({
          mode: 'edit',
          annotation: ann,
          position: { top, left },
          anchorText: ann.anchor_text,
          onClose: () => pin.classList.remove('active'),
        });
        return;
      }

      // Highlight click
      const highlight = e.target.closest('.annotation-highlight');
      if (highlight) {
        e.stopPropagation();
        const annotationId = parseInt(highlight.dataset.annotationId);
        const ann = annotationsRef.current.find((a) => a.id === annotationId);
        if (!ann) return;

        const spanRect = highlight.getBoundingClientRect();
        const top = spanRect.bottom - viewerRect.top + viewer.scrollTop + 8;
        let left = spanRect.left - viewerRect.left + viewer.scrollLeft - 10;
        if (left + 320 > viewer.clientWidth - 16) left = viewer.clientWidth - 320 - 16;
        if (left < 8) left = 8;

        setPopover({
          mode: 'edit',
          annotation: ann,
          position: { top, left },
          anchorText: ann.anchor_text,
        });
      }
    }

    const entries = overlaysRef.current;
    entries.forEach((o) => o.wrapperEl.addEventListener('click', handleWrapperClick));
    return () => {
      entries.forEach((o) => o.wrapperEl.removeEventListener('click', handleWrapperClick));
    };
  }, []);

  // ------------------------------------------------------------------
  // Add mode (pin placement overlays)
  // ------------------------------------------------------------------
  useEffect(() => {
    const addBtn = document.getElementById('btn-add-annotation');
    if (addBtn) addBtn.classList.toggle('active', isAddMode);

    if (isAddMode) {
      overlaysRef.current.forEach((o) => {
        const overlay = document.createElement('div');
        overlay.className = 'pdf-page-overlay add-mode';
        overlay.dataset.pageNumber = o.pageNumber;
        overlay.addEventListener('click', (e) => handleOverlayClick(e, o.pageNumber, overlay));
        o.wrapperEl.appendChild(overlay);
        o.overlayEl = overlay;
      });
    } else {
      overlaysRef.current.forEach((o) => {
        if (o.overlayEl) {
          o.overlayEl.remove();
          o.overlayEl = null;
        }
      });
      const temp = document.querySelector('.annotation-pin--new');
      if (temp) temp.remove();
    }

    return () => {
      overlaysRef.current.forEach((o) => {
        if (o.overlayEl) {
          o.overlayEl.remove();
          o.overlayEl = null;
        }
      });
    };
  }, [isAddMode]);

  function handleOverlayClick(e, pageNumber, overlayEl) {
    const rect = overlayEl.getBoundingClientRect();
    const xPercent = Math.max(0, Math.min(100, ((e.clientX - rect.left) / rect.width) * 100));
    const yPercent = Math.max(0, Math.min(100, ((e.clientY - rect.top) / rect.height) * 100));

    const entry = overlaysRef.current.find((o) => o.pageNumber === pageNumber);
    const wrapperEl = entry ? entry.wrapperEl : overlayEl.parentElement;

    // Remove overlays synchronously before creating temp pin
    overlaysRef.current.forEach((o) => {
      if (o.overlayEl) {
        o.overlayEl.remove();
        o.overlayEl = null;
      }
    });
    setIsAddMode(false);

    // Temp pin
    const tempPin = document.createElement('div');
    tempPin.className = 'annotation-pin annotation-pin--new';
    tempPin.style.left = xPercent + '%';
    tempPin.style.top = yPercent + '%';
    wrapperEl.appendChild(tempPin);

    // Position popover below pin
    const viewer = document.getElementById('pdf-viewer');
    const viewerRect = viewer.getBoundingClientRect();
    const pinRect = tempPin.getBoundingClientRect();
    const top = pinRect.bottom - viewerRect.top + viewer.scrollTop + 8;
    let left = pinRect.left - viewerRect.left + viewer.scrollLeft - 10;
    if (left + 320 > viewer.clientWidth - 16) left = viewer.clientWidth - 320 - 16;
    if (left < 8) left = 8;

    setPopover({
      mode: 'create_pin',
      position: { top, left },
      pageNumber,
      xPercent,
      yPercent,
      tempPin,
    });
  }

  // ------------------------------------------------------------------
  // Text selection → highlight action button
  // ------------------------------------------------------------------
  useEffect(() => {
    function handleMouseUp() {
      setTimeout(() => {
        const selection = window.getSelection();
        if (!selection || selection.isCollapsed || !selection.toString().trim()) return;

        const selectedText = selection.toString().trim();
        if (selectedText.length < 2) return;

        const anchorNode = selection.anchorNode;
        const textLayer = anchorNode ? anchorNode.parentElement.closest('.textLayer') : null;
        if (!textLayer) return;

        const wrapper = textLayer.closest('.pdf-page-canvas-wrapper');
        if (!wrapper) return;

        const pageNumber = parseInt(wrapper.dataset.pageNumber);
        const range = selection.getRangeAt(0);
        const rect = range.getBoundingClientRect();

        const viewer = document.getElementById('pdf-viewer');
        if (!viewer) return;
        const viewerRect = viewer.getBoundingClientRect();

        const top = rect.bottom - viewerRect.top + viewer.scrollTop + 4;
        let left = rect.left - viewerRect.left + viewer.scrollLeft;
        if (left + 140 > viewer.clientWidth) left = viewer.clientWidth - 150;
        if (left < 8) left = 8;

        setHighlightAction({
          text: selectedText,
          pageNumber,
          position: { top, left },
          selectionRect: rect,
        });
      }, 10);
    }

    function handleMouseDown(e) {
      if (!e.target.closest('.highlight-action-btn')) {
        setHighlightAction(null);
      }
    }

    document.addEventListener('mouseup', handleMouseUp);
    document.addEventListener('mousedown', handleMouseDown);
    return () => {
      document.removeEventListener('mouseup', handleMouseUp);
      document.removeEventListener('mousedown', handleMouseDown);
    };
  }, []);

  function handleHighlightActionClick() {
    if (!highlightAction) return;
    const { text, pageNumber, selectionRect } = highlightAction;
    setHighlightAction(null);

    const viewer = document.getElementById('pdf-viewer');
    if (!viewer) return;
    const viewerRect = viewer.getBoundingClientRect();

    const top = selectionRect.bottom - viewerRect.top + viewer.scrollTop + 8;
    let left = selectionRect.left - viewerRect.left + viewer.scrollLeft - 10;
    if (left + 320 > viewer.clientWidth - 16) left = viewer.clientWidth - 320 - 16;
    if (left < 8) left = 8;

    window.getSelection().removeAllRanges();

    setPopover({
      mode: 'create_highlight',
      position: { top, left },
      anchorText: text,
      pageNumber,
    });
  }

  // ------------------------------------------------------------------
  // Popover handlers
  // ------------------------------------------------------------------
  async function handlePopoverSave(content, scope) {
    if (!content.trim() || !popover) return;

    if (popover.mode === 'create_pin') {
      const created = await createAnnotation({
        annotation_type: 'pin',
        page_number: popover.pageNumber,
        x_percent: popover.xPercent,
        y_percent: popover.yPercent,
        content: content.trim(),
        scope,
      });
      if (created && popover.tempPin) popover.tempPin.remove();
    } else if (popover.mode === 'create_highlight') {
      await createAnnotation({
        annotation_type: 'highlight',
        page_number: popover.pageNumber,
        anchor_text: popover.anchorText,
        content: content.trim(),
        scope,
      });
    } else if (popover.mode === 'edit') {
      await updateAnnotationApi(popover.annotation.id, content.trim(), scope);
    }

    if (popover.onClose) popover.onClose();
    setPopover(null);
  }

  function handlePopoverCancel() {
    if (popover?.tempPin) popover.tempPin.remove();
    if (popover?.onClose) popover.onClose();
    setPopover(null);
  }

  async function handlePopoverDelete() {
    if (!popover?.annotation) return;
    if (!confirm('Delete this note?')) return;
    await deleteAnnotationApi(popover.annotation.id);
    if (popover.onClose) popover.onClose();
    setPopover(null);
  }

  async function handleSendToJournal() {
    if (!popover?.annotation) return null;
    return await sendToJournalApi(popover.annotation.id);
  }

  // ------------------------------------------------------------------
  // Sidebar open/close & badge count sync
  // ------------------------------------------------------------------
  useEffect(() => {
    const sidebar = document.getElementById('annotation-sidebar');
    if (sidebar) sidebar.classList.toggle('open', sidebarOpen);
    const btn = document.getElementById('btn-toggle-sidebar');
    if (btn) btn.classList.toggle('active', sidebarOpen);
  }, [sidebarOpen]);

  useEffect(() => {
    const badge = document.getElementById('annotation-count-badge');
    if (!badge) return;
    badge.textContent = annotations.length;
    badge.style.display = annotations.length > 0 ? 'inline' : 'none';
  }, [annotations]);

  // ------------------------------------------------------------------
  // Scroll to annotation (sidebar click handler)
  // ------------------------------------------------------------------
  const scrollToAnnotation = useCallback((pageNumber, annotationId) => {
    const entry = overlaysRef.current.find((o) => o.pageNumber === pageNumber);
    if (!entry) return;

    let scrollTarget = entry.wrapperEl;
    if (annotationId) {
      const pin = entry.wrapperEl.querySelector(
        `.annotation-pin[data-annotation-id="${annotationId}"]`,
      );
      if (pin) {
        scrollTarget = pin;
      } else {
        const span = entry.wrapperEl.querySelector(
          `.annotation-highlight[data-annotation-id="${annotationId}"]`,
        );
        if (span) scrollTarget = span;
      }
    }

    scrollTarget.scrollIntoView({ behavior: 'smooth', block: 'center' });

    if (annotationId) {
      setTimeout(() => {
        const pin = entry.wrapperEl.querySelector(
          `.annotation-pin[data-annotation-id="${annotationId}"]`,
        );
        if (pin) {
          pin.classList.add('highlight');
          setTimeout(() => pin.classList.remove('highlight'), 1000);
        }
        entry.wrapperEl
          .querySelectorAll(`.annotation-highlight[data-annotation-id="${annotationId}"]`)
          .forEach((s) => {
            s.style.transition = 'background-color 0.3s';
            s.style.backgroundColor = 'rgba(255, 235, 59, 0.8)';
            setTimeout(() => {
              s.style.backgroundColor = '';
            }, 1000);
          });
      }, 400);
    }
  }, []);

  // ------------------------------------------------------------------
  // Escape key
  // ------------------------------------------------------------------
  useEffect(() => {
    function handler(e) {
      if (e.key === 'Escape') {
        setIsAddMode(false);
        setPopover((prev) => {
          if (prev?.tempPin) prev.tempPin.remove();
          if (prev?.onClose) prev.onClose();
          return null;
        });
        setHighlightAction(null);
      }
    }
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  // ------------------------------------------------------------------
  // Toolbar button wiring
  // ------------------------------------------------------------------
  useEffect(() => {
    const addBtn = document.getElementById('btn-add-annotation');
    function handler() {
      setIsAddMode((prev) => !prev);
      setPopover(null);
      setHighlightAction(null);
    }
    if (addBtn) addBtn.addEventListener('click', handler);
    return () => {
      if (addBtn) addBtn.removeEventListener('click', handler);
    };
  }, []);

  useEffect(() => {
    const btn = document.getElementById('btn-toggle-sidebar');
    function handler() {
      setSidebarOpen((prev) => !prev);
    }
    if (btn) btn.addEventListener('click', handler);
    return () => {
      if (btn) btn.removeEventListener('click', handler);
    };
  }, []);

  // ------------------------------------------------------------------
  // Global API (backward compat for sidebar close button onclick)
  // ------------------------------------------------------------------
  useEffect(() => {
    window.DocumentAnnotations = {
      toggleSidebar: () => setSidebarOpen((prev) => !prev),
      enterAddMode: () => setIsAddMode(true),
    };
    return () => {
      delete window.DocumentAnnotations;
    };
  }, []);

  // ------------------------------------------------------------------
  // Render (portals into existing template DOM)
  // ------------------------------------------------------------------
  const viewer = document.getElementById('pdf-viewer');
  const sidebarList = document.getElementById('annotation-sidebar-list');

  return (
    <>
      {/* Sidebar list */}
      {sidebarList &&
        createPortal(
          <AnnotationSidebar annotations={annotations} onScrollTo={scrollToAnnotation} />,
          sidebarList,
        )}

      {/* Popover */}
      {popover &&
        viewer &&
        createPortal(
          <AnnotationPopover
            mode={popover.mode}
            annotation={popover.annotation}
            position={popover.position}
            anchorText={popover.anchorText}
            companyName={companyName}
            onSave={handlePopoverSave}
            onCancel={handlePopoverCancel}
            onDelete={popover.mode === 'edit' ? handlePopoverDelete : null}
            onSendToJournal={popover.mode === 'edit' ? handleSendToJournal : null}
          />,
          viewer,
        )}

      {/* Highlight action button */}
      {highlightAction &&
        viewer &&
        createPortal(
          <div
            className="highlight-action-btn"
            style={{
              top: highlightAction.position.top + 'px',
              left: highlightAction.position.left + 'px',
            }}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              handleHighlightActionClick();
            }}
          >
            <i className="bi bi-chat-quote" /> Add Note
          </div>,
          viewer,
        )}
    </>
  );
}

function truncate(text, maxLen) {
  if (!text) return '';
  return text.length > maxLen ? text.substring(0, maxLen) + '...' : text;
}
