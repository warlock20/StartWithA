import { useRef } from 'react';
import { NOTE_TYPE_META, escapeHtml } from './utils';

/**
 * NoteCard — Draggable, expandable note card within a canvas section.
 *
 * Props:
 *   note: { id, title, contentHtml, sourceUrl, sourceTitle, tags, noteType, sectionId }
 *   isExpanded: bool
 *   openMenuId: number|null
 *   onToggleExpand: (noteId) => void
 *   onToggleMenu: (noteId) => void
 *   onView: (noteId) => void
 *   onEdit: (noteId) => void
 *   onDelete: (noteId) => void
 *   onDragStart: (noteId, e) => void
 *   onDragEnd: (e) => void
 */
export function NoteCard({
  note,
  isExpanded,
  openMenuId,
  onToggleExpand,
  onToggleMenu,
  onView,
  onEdit,
  onDelete,
  onDragStart,
  onDragEnd,
}) {
  var isDragging = useRef(false);
  var typeMeta = NOTE_TYPE_META[note.noteType] || NOTE_TYPE_META.note;
  var tagsArray = note.tags ? note.tags.split(',').map(function (t) { return t.trim(); }).filter(Boolean) : [];

  function handleDragStart(e) {
    isDragging.current = true;
    onDragStart(note.id, e);
  }

  function handleDragEnd(e) {
    isDragging.current = false;
    onDragEnd(e);
  }

  function handleClick(e) {
    if (e.target.closest('.note-card-menu-wrapper') || e.target.closest('.note-card-dropdown')) return;
    if (isDragging.current) return;
    if (e.target.closest('a')) return;
    onToggleExpand(note.id);
  }

  function handleMenuClick(e) {
    e.stopPropagation();
    onToggleMenu(note.id);
  }

  return (
    <div
      className={'note-card' + (isExpanded ? ' expanded' : '')}
      draggable="true"
      data-note-id={note.id}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onClick={handleClick}
    >
      <div className="note-card-header">
        <h3 className="note-card-title">{note.title}</h3>
        <div className="note-card-menu-wrapper">
          <button className="note-card-menu-btn" onClick={handleMenuClick}>
            <i className="bi bi-three-dots-vertical" />
          </button>
          <div
            className="note-card-dropdown"
            style={{ display: openMenuId === note.id ? 'block' : 'none' }}
          >
            <button onClick={function (e) { e.stopPropagation(); onView(note.id); }}>
              <i className="bi bi-eye" /> View Full Note
            </button>
            <button onClick={function (e) { e.stopPropagation(); onEdit(note.id); }}>
              <i className="bi bi-pencil" /> Edit
            </button>
            <button
              className="text-danger"
              onClick={function (e) { e.stopPropagation(); onDelete(note.id); }}
            >
              <i className="bi bi-trash" /> Delete
            </button>
          </div>
        </div>
      </div>

      <div
        className="note-card-content"
        dangerouslySetInnerHTML={{ __html: note.contentHtml || '' }}
      />

      <div className="note-card-footer">
        <div className={'note-card-type ' + (typeMeta.className || '')}>
          <i className={'bi ' + typeMeta.icon} /> {typeMeta.label}
        </div>
        {note.sourceTitle && note.noteType === 'company_insight' && (
          <span className="note-card-source-title">{note.sourceTitle}</span>
        )}
        {note.sourceUrl && (
          <a
            href={note.sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="note-card-source"
            onClick={function (e) { e.stopPropagation(); }}
          >
            <i className="bi bi-box-arrow-up-right" /> Source
          </a>
        )}
      </div>

      {tagsArray.length > 0 && (
        <div className="note-card-tags">
          {tagsArray.map(function (tag) {
            return (
              <span key={tag} className="note-card-tag">
                {tag}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}
