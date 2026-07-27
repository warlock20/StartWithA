import { Modal } from './Modal';

/**
 * ViewNoteModal — Read-only note viewer.
 *
 * Props:
 *   isOpen: bool
 *   note: { id, title, contentHtml, sourceUrl, sourceTitle, tags } | null
 *   onEdit: (noteId) => void
 *   onClose: () => void
 */
export function ViewNoteModal({ isOpen, note, onEdit, onClose }) {
  if (!note) return null;

  var tagsArray = note.tags
    ? note.tags.split(',').map(function (t) { return t.trim(); }).filter(Boolean)
    : [];

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={note.title}
      size="modal-lg modal-dialog-scrollable"
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={function () { onEdit(note.id); }}
          >
            <i className="bi bi-pencil" /> Edit Note
          </button>
        </>
      }
    >
      <div
        className="note-view-content"
        dangerouslySetInnerHTML={{ __html: note.contentHtml || '' }}
      />

      {(note.sourceUrl || tagsArray.length > 0) && (
        <div style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid #e5e7eb' }}>
          {note.sourceUrl && (
            <div style={{ marginBottom: '1rem' }}>
              <p className="text-muted mb-1" style={{ fontSize: '0.875rem', fontWeight: 600 }}>
                <i className="bi bi-link-45deg" /> Source
              </p>
              <a
                href={note.sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: '#3b82f6', textDecoration: 'none' }}
              >
                {note.sourceTitle || note.sourceUrl}
              </a>
            </div>
          )}

          {tagsArray.length > 0 && (
            <div>
              <p className="text-muted mb-2" style={{ fontSize: '0.875rem', fontWeight: 600 }}>
                <i className="bi bi-tags" /> Tags
              </p>
              <div>
                {tagsArray.map(function (tag) {
                  return (
                    <span key={tag} className="note-card-tag" style={{ marginRight: '0.5rem' }}>
                      {tag}
                    </span>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}
