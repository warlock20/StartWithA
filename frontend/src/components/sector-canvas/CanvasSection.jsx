import { NoteCard } from './NoteCard';

/**
 * CanvasSection — A section on the research canvas with header + note grid.
 *
 * Props:
 *   section: { id, title, description, icon, notes: [] }
 *   isInbox: bool (true for the collector/inbox section)
 *   expandedNotes: Set
 *   openMenuId: number|null
 *   dragOverSectionId: number|string|null
 *   onAddNote: (sectionId) => void
 *   onEditSection: (section) => void
 *   onDeleteSection: (sectionId) => void
 *   onToggleExpand, onToggleMenu, onViewNote, onEditNote, onDeleteNote
 *   onDragStart, onDragEnd, onDragOver, onDrop, onDragLeave
 */
export function CanvasSection({
  section,
  isInbox,
  expandedNotes,
  openMenuId,
  dragOverSectionId,
  onAddNote,
  onEditSection,
  onDeleteSection,
  onToggleExpand,
  onToggleMenu,
  onViewNote,
  onEditNote,
  onDeleteNote,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDrop,
  onDragLeave,
}) {
  var sectionId = isInbox ? '' : section.id;
  var isDropTarget =
    dragOverSectionId !== null && String(dragOverSectionId) === String(sectionId);

  function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    onDragOver(sectionId);
  }

  function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    onDrop(sectionId);
  }

  function handleDragLeave() {
    onDragLeave();
  }

  return (
    <div
      className={
        'canvas-section' +
        (isInbox ? ' canvas-section--inbox' : '') +
        (isDropTarget ? ' drop-zone-active' : '')
      }
      data-section-id={sectionId}
    >
      <div className="canvas-section-header">
        <div className="canvas-section-title">
          {section.icon && <span className="canvas-section-icon">{section.icon}</span>}
          <h2>{section.title}</h2>
          {isInbox && (
            <span className="badge bg-secondary ms-2">{section.notes.length}</span>
          )}
        </div>
        {!isInbox && (
          <div className="canvas-section-actions">
            <button
              className="btn btn-sm btn-outline-primary"
              onClick={function () { onAddNote(section.id); }}
            >
              <i className="bi bi-plus" />
            </button>
            <button
              className="btn btn-sm btn-outline-secondary"
              onClick={function () { onEditSection(section); }}
            >
              <i className="bi bi-pencil" />
            </button>
            <button
              className="btn btn-sm btn-outline-danger"
              onClick={function () { onDeleteSection(section.id); }}
            >
              <i className="bi bi-trash" />
            </button>
          </div>
        )}
      </div>

      {section.description && !isInbox && (
        <div className="canvas-section-description">{section.description}</div>
      )}

      <div
        className={'note-cards-grid' + (isDropTarget ? ' drop-zone-active' : '')}
        data-section-id={sectionId}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onDragLeave={handleDragLeave}
      >
        {section.notes.length > 0 ? (
          section.notes.map(function (note) {
            return (
              <NoteCard
                key={note.id}
                note={note}
                isExpanded={expandedNotes.has(note.id)}
                openMenuId={openMenuId}
                onToggleExpand={onToggleExpand}
                onToggleMenu={onToggleMenu}
                onView={onViewNote}
                onEdit={onEditNote}
                onDelete={onDeleteNote}
                onDragStart={onDragStart}
                onDragEnd={onDragEnd}
              />
            );
          })
        ) : !isInbox ? (
          <button
            className="add-note-btn"
            onClick={function () { onAddNote(section.id); }}
          >
            <i className="bi bi-plus-circle" /> Add First Note
          </button>
        ) : null}
      </div>
    </div>
  );
}
