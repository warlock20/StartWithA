import { useState, useEffect, useRef, useCallback } from 'react';
import { Modal } from './Modal';

/**
 * NoteModal — Create/edit a note with BlockNote editor.
 *
 * The BlockNote editor is a separate React island initialized via
 * window.initBlockNoteEditor. We manage its lifecycle here:
 * mount when modal opens, read content on save.
 *
 * Props:
 *   isOpen: bool
 *   editNote: { id, title, content, sourceUrl, sourceTitle, tags, sectionId } | null
 *   sectionId: number|null (target section for new notes)
 *   onSave: ({ id?, title, content, sectionId, sourceUrl, sourceTitle, tags }) => void
 *   onClose: () => void
 */
export function NoteModal({ isOpen, editNote, sectionId, onSave, onClose }) {
  var [title, setTitle] = useState('');
  var [sourceUrl, setSourceUrl] = useState('');
  var [sourceTitle, setSourceTitle] = useState('');
  var [tags, setTags] = useState('');
  var [targetSectionId, setTargetSectionId] = useState(null);
  var editorRootRef = useRef(null);
  var editorReadyRef = useRef(false);
  var editorContainerId = 'react-note-content-editor';

  // Populate form when opening
  useEffect(function () {
    if (!isOpen) return;
    if (editNote) {
      setTitle(editNote.title || '');
      setSourceUrl(editNote.sourceUrl || '');
      setSourceTitle(editNote.sourceTitle || '');
      setTags(editNote.tags || '');
      setTargetSectionId(editNote.sectionId || null);
    } else {
      setTitle('');
      setSourceUrl('');
      setSourceTitle('');
      setTags('');
      setTargetSectionId(sectionId || null);
    }
    editorReadyRef.current = false;
  }, [isOpen, editNote, sectionId]);

  // Initialize BlockNote when modal is open
  useEffect(function () {
    if (!isOpen) {
      // Cleanup editor when closing
      if (editorRootRef.current) {
        try { editorRootRef.current.unmount(); } catch (e) { /* ignore */ }
        editorRootRef.current = null;
      }
      editorReadyRef.current = false;
      return;
    }

    // Wait for DOM element and BlockNote
    var pollId = setInterval(function () {
      var container = document.getElementById(editorContainerId);
      if (container && window.initBlockNoteEditor) {
        clearInterval(pollId);
        // Clear container
        container.innerHTML = '';
        editorRootRef.current = window.initBlockNoteEditor(editorContainerId, {
          placeholder: 'Write your note here... Type "/" for commands',
          onSave: null,
        });

        // Wait for editor instance to be ready, then set content if editing
        var readyPoll = setInterval(function () {
          if (window.blockNoteEditorInstance) {
            clearInterval(readyPoll);
            window.noteEditorInstance = window.blockNoteEditorInstance;
            editorReadyRef.current = true;

            // Load existing content for edit mode
            if (editNote && editNote.content) {
              loadEditContent(editNote.content);
            }
          }
        }, 50);

        setTimeout(function () { clearInterval(readyPoll); }, 3000);
      }
    }, 100);

    var timeoutId = setTimeout(function () { clearInterval(pollId); }, 5000);

    return function () {
      clearInterval(pollId);
      clearTimeout(timeoutId);
    };
  }, [isOpen, editNote]);

  var loadEditContent = useCallback(function (content) {
    if (!window.noteEditorInstance || !window.noteEditorInstance.editor) return;
    // Decode HTML entities
    var tempDiv = document.createElement('div');
    tempDiv.innerHTML = content;
    var decoded = tempDiv.innerHTML;
    try {
      var blocks = JSON.parse(decoded);
      if (Array.isArray(blocks)) {
        window.noteEditorInstance.editor.replaceBlocks(
          window.noteEditorInstance.editor.document,
          blocks
        );
      }
    } catch (e) {
      // Not JSON — it's HTML, use insertHTML
      if (window.noteEditorInstance.insertHTML) {
        window.noteEditorInstance.editor.replaceBlocks(
          window.noteEditorInstance.editor.document,
          [{ type: 'paragraph', content: [] }]
        );
        window.noteEditorInstance.insertHTML(decoded);
      }
    }
  }, []);

  function handleSave() {
    if (!window.noteEditorInstance || !window.noteEditorInstance.editor) {
      alert('Editor is not ready. Please wait a moment and try again.');
      return;
    }

    var trimmedTitle = title.trim();
    var blocks = window.noteEditorInstance.editor.document;
    var content = JSON.stringify(blocks);
    var textContent = blocks
      .map(function (block) {
        if (block.content && Array.isArray(block.content)) {
          return block.content
            .filter(function (item) { return item && item.type === 'text'; })
            .map(function (item) { return item.text || ''; })
            .join('');
        }
        return '';
      })
      .join(' ')
      .trim();

    if (!trimmedTitle) {
      alert('Please enter a title for the note');
      return;
    }
    if (!textContent) {
      alert('Please enter content for the note');
      return;
    }

    onSave({
      id: editNote ? editNote.id : undefined,
      title: trimmedTitle,
      content: content,
      sectionId: targetSectionId,
      sourceUrl: sourceUrl.trim() || null,
      sourceTitle: sourceTitle.trim() || null,
      tags: tags.trim() || null,
    });
  }

  var isEdit = editNote !== null;
  var modalTitle = isEdit
    ? 'Edit Note'
    : targetSectionId
      ? 'Add Note to Section'
      : 'Create Note (will go to Collector)';

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={modalTitle}
      size="modal-lg modal-dialog-scrollable"
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn btn-primary" onClick={handleSave}>
            <i className="bi bi-check-circle" />{' '}
            {isEdit ? 'Update Note' : 'Create Note'}
          </button>
        </>
      }
    >
      <div className="mb-3">
        <label className="form-label">Title *</label>
        <input
          type="text"
          className="form-control"
          placeholder="Note title"
          value={title}
          onChange={function (e) { setTitle(e.target.value); }}
          autoFocus
        />
      </div>

      <div className="mb-4">
        <label className="form-label">Content *</label>
        <div id={editorContainerId} className="blocknote-form-editor" />
      </div>

      <div className="row">
        <div className="col-md-6 mb-3">
          <label className="form-label">Source URL (optional)</label>
          <input
            type="url"
            className="form-control"
            placeholder="https://..."
            value={sourceUrl}
            onChange={function (e) { setSourceUrl(e.target.value); }}
          />
        </div>
        <div className="col-md-6 mb-3">
          <label className="form-label">Source Title (optional)</label>
          <input
            type="text"
            className="form-control"
            placeholder="Article title, etc."
            value={sourceTitle}
            onChange={function (e) { setSourceTitle(e.target.value); }}
          />
        </div>
      </div>

      <div className="mb-3">
        <label className="form-label">Tags (optional)</label>
        <input
          type="text"
          className="form-control"
          placeholder="e.g., competitive advantage, pricing"
          value={tags}
          onChange={function (e) { setTags(e.target.value); }}
        />
        <small className="text-muted">Separate multiple tags with commas</small>
      </div>
    </Modal>
  );
}
