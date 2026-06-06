import { useState, useEffect, useRef } from 'react';

/**
 * Annotation popover editor — used for creating and editing pin/highlight notes.
 * Rendered via React Portal into #pdf-viewer for correct absolute positioning.
 */
export function AnnotationPopover({
  mode,
  annotation,
  position,
  anchorText,
  companyName,
  onSave,
  onCancel,
  onDelete,
  onSendToJournal,
}) {
  const [content, setContent] = useState(annotation?.content || '');
  const [scope, setScope] = useState(annotation?.scope || 'company');
  const [journalStatus, setJournalStatus] = useState(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) {
      setTimeout(() => textareaRef.current.focus(), 50);
    }
  }, []);

  function handleKeyDown(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      onSave(content, scope);
    }
  }

  async function handleJournal() {
    const result = await onSendToJournal();
    if (result?.success) {
      setJournalStatus({ text: 'Sent to journal', color: '#198754' });
    } else {
      setJournalStatus({ text: 'Failed to send', color: '#dc3545' });
    }
  }

  const isEdit = mode === 'edit';

  return (
    <div
      className="annotation-popover"
      style={{ top: position.top + 'px', left: position.left + 'px' }}
    >
      {anchorText && (
        <div
          className="mb-2"
          style={{
            fontSize: '0.8rem',
            color: '#555',
            borderLeft: '3px solid #fbc02d',
            padding: '0.375rem 0.5rem',
            background: '#fffde7',
            borderRadius: '0 0.25rem 0.25rem 0',
            maxHeight: '80px',
            overflowY: 'auto',
          }}
        >
          {anchorText.length > 200 ? anchorText.substring(0, 200) + '...' : anchorText}
        </div>
      )}

      <textarea
        ref={textareaRef}
        placeholder={anchorText ? 'Add your comment...' : 'Write your note...'}
        value={content}
        onChange={(e) => setContent(e.target.value)}
        onKeyDown={handleKeyDown}
      />

      <div className="d-flex align-items-center gap-2 mt-2">
        <small className="text-muted">Scope:</small>
        <select
          className="form-select form-select-sm"
          style={{ width: 'auto' }}
          value={scope}
          onChange={(e) => setScope(e.target.value)}
        >
          <option value="company">{companyName || 'Company'}</option>
          <option value="sector">Sector</option>
          <option value="general">General</option>
        </select>
      </div>

      <div className="popover-actions">
        <button className="btn btn-sm btn-primary" onClick={() => onSave(content, scope)}>
          Save
        </button>
        <button className="btn btn-sm btn-outline-secondary" onClick={onCancel}>
          Cancel
        </button>
        {isEdit && (
          <div className="popover-actions-right">
            <button
              className="btn btn-sm btn-outline-success"
              onClick={handleJournal}
              disabled={!!journalStatus}
            >
              <i className="bi bi-journal-arrow-up me-1" />
              Journal
            </button>
            <button
              className="btn btn-sm btn-outline-danger"
              onClick={onDelete}
              title="Delete note"
            >
              <i className="bi bi-trash" />
            </button>
          </div>
        )}
      </div>
      {journalStatus && (
        <span className="popover-meta" style={{ display: 'inline', color: journalStatus.color }}>
          {journalStatus.text}
        </span>
      )}
    </div>
  );
}
