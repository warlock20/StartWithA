import { useState, useEffect, useRef, useCallback } from 'react';
import { CanvasSection } from './CanvasSection';
import { SectionModal } from './SectionModal';
import { NoteModal } from './NoteModal';
import { ViewNoteModal } from './ViewNoteModal';
import { showToast, blocknoteToPreviewHtml } from './utils';

/**
 * SectorCanvas — Main React island for the sector research canvas.
 *
 * Manages sections, notes, drag-and-drop, and CRUD modals.
 *
 * Props:
 *   sections: Array of { id, title, description, icon, notes: [] }
 *   inboxNotes: Array of note objects
 *   urls: { createSection, updateSection, deleteSection, createNote, updateNote, deleteNote }
 */
export function SectorCanvas({ sections: initialSections, inboxNotes: initialInbox, urls }) {
  var [sections, setSections] = useState(initialSections || []);
  var [inboxNotes, setInboxNotes] = useState(initialInbox || []);
  var [expandedNotes, setExpandedNotes] = useState(new Set());
  var [openMenuId, setOpenMenuId] = useState(null);
  var [draggedNoteId, setDraggedNoteId] = useState(null);
  var [dragOverSectionId, setDragOverSectionId] = useState(null);

  // Modal states
  var [sectionModal, setSectionModal] = useState({ isOpen: false, editSection: null });
  var [noteModal, setNoteModal] = useState({ isOpen: false, editNote: null, sectionId: null });
  var [viewModal, setViewModal] = useState({ isOpen: false, note: null });

  // Close menus on outside click
  useEffect(function () {
    function handleClick(e) {
      if (!e.target.closest('.note-card-menu-wrapper')) {
        setOpenMenuId(null);
      }
    }
    document.addEventListener('click', handleClick);
    return function () { document.removeEventListener('click', handleClick); };
  }, []);

  // Expose global functions for backward compat (used by toolbar onclick in focus template)
  useEffect(function () {
    window.createNewNote = function () {
      setNoteModal({ isOpen: true, editNote: null, sectionId: null });
    };
    window.createNewSection = function () {
      setSectionModal({ isOpen: true, editSection: null });
    };
    window.addNoteToSection = function (sectionId) {
      setNoteModal({ isOpen: true, editNote: null, sectionId: sectionId });
    };
    window.createQuickNote = handleQuickNote;

    return function () {
      delete window.createNewNote;
      delete window.createNewSection;
      delete window.addNoteToSection;
      delete window.createQuickNote;
    };
  }, []);

  // -----------------------------------------------------------------
  // Helper: find a note by ID across sections and inbox
  // -----------------------------------------------------------------
  var findNote = useCallback(function (noteId) {
    for (var i = 0; i < sections.length; i++) {
      for (var j = 0; j < sections[i].notes.length; j++) {
        if (sections[i].notes[j].id === noteId) return sections[i].notes[j];
      }
    }
    for (var k = 0; k < inboxNotes.length; k++) {
      if (inboxNotes[k].id === noteId) return inboxNotes[k];
    }
    return null;
  }, [sections, inboxNotes]);

  // -----------------------------------------------------------------
  // Note card handlers
  // -----------------------------------------------------------------

  function handleToggleExpand(noteId) {
    setExpandedNotes(function (prev) {
      var next = new Set(prev);
      if (next.has(noteId)) next.delete(noteId);
      else next.add(noteId);
      return next;
    });
  }

  function handleToggleMenu(noteId) {
    setOpenMenuId(function (prev) { return prev === noteId ? null : noteId; });
  }

  // -----------------------------------------------------------------
  // Drag & Drop
  // -----------------------------------------------------------------

  function handleDragStart(noteId) {
    setDraggedNoteId(noteId);
  }

  function handleDragEnd() {
    setDraggedNoteId(null);
    setDragOverSectionId(null);
  }

  function handleDragOver(sectionId) {
    setDragOverSectionId(sectionId);
  }

  function handleDragLeave() {
    setDragOverSectionId(null);
  }

  function handleDrop(targetSectionId) {
    setDragOverSectionId(null);
    if (!draggedNoteId) return;

    var noteId = draggedNoteId;
    setDraggedNoteId(null);

    // API call to move note
    showToast('Moving\u2026', 'loading');
    fetch('/sectors/note/' + noteId + '/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ section_id: targetSectionId || null }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success) {
          moveNoteInState(noteId, targetSectionId || null);
          showToast('Note moved', 'success');
        } else {
          alert('Error moving note: ' + (data.error || 'Unknown error'));
        }
      })
      .catch(function () { alert('Error moving note'); });
  }

  function moveNoteInState(noteId, targetSectionId) {
    var movedNote = null;

    // Remove from inbox
    setInboxNotes(function (prev) {
      var found = prev.find(function (n) { return n.id === noteId; });
      if (found) {
        movedNote = { ...found, sectionId: targetSectionId };
        return prev.filter(function (n) { return n.id !== noteId; });
      }
      return prev;
    });

    // Remove from sections
    setSections(function (prev) {
      return prev.map(function (s) {
        var found = s.notes.find(function (n) { return n.id === noteId; });
        if (found) {
          movedNote = { ...found, sectionId: targetSectionId };
          return { ...s, notes: s.notes.filter(function (n) { return n.id !== noteId; }) };
        }
        return s;
      });
    });

    // Add to target (use setTimeout to ensure removal is processed first)
    setTimeout(function () {
      if (!movedNote) return;
      if (targetSectionId) {
        setSections(function (prev) {
          return prev.map(function (s) {
            if (String(s.id) === String(targetSectionId)) {
              return { ...s, notes: [...s.notes, movedNote] };
            }
            return s;
          });
        });
      } else {
        setInboxNotes(function (prev) { return [...prev, movedNote]; });
      }
    }, 0);
  }

  // -----------------------------------------------------------------
  // Section CRUD
  // -----------------------------------------------------------------

  function handleSaveSection(data) {
    var isEdit = data.id !== undefined;
    var url = isEdit
      ? urls.updateSection.replace('0', data.id)
      : urls.createSection;

    showToast('Saving\u2026', 'loading');
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: data.title,
        description: data.description,
        icon: data.icon,
      }),
    })
      .then(function (r) { return r.json(); })
      .then(function (result) {
        if (result.success) {
          setSectionModal({ isOpen: false, editSection: null });
          if (isEdit) {
            setSections(function (prev) {
              return prev.map(function (s) {
                if (s.id === data.id) {
                  return { ...s, title: data.title, description: data.description, icon: data.icon };
                }
                return s;
              });
            });
            showToast('Section updated', 'success');
          } else {
            var newSection = {
              id: result.section.id,
              title: data.title,
              description: data.description,
              icon: data.icon,
              notes: [],
            };
            setSections(function (prev) { return [...prev, newSection]; });
            showToast('Section created', 'success');
          }
        } else {
          alert('Error saving section: ' + (result.error || 'Unknown error'));
        }
      })
      .catch(function (err) {
        alert('Error saving section');
        console.error(err);
      });
  }

  function handleDeleteSection(sectionId) {
    if (!confirm('Delete this section? All notes will be moved to the Collector.')) return;

    showToast('Deleting\u2026', 'loading');
    fetch(urls.deleteSection.replace('0', sectionId), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success) {
          setSections(function (prev) {
            return prev.filter(function (s) { return s.id !== sectionId; });
          });
          showToast('Section deleted', 'success');
        } else {
          alert('Error deleting section: ' + (data.error || 'Unknown error'));
        }
      })
      .catch(function (err) {
        alert('Error deleting section');
        console.error(err);
      });
  }

  // -----------------------------------------------------------------
  // Note CRUD
  // -----------------------------------------------------------------

  function handleViewNote(noteId) {
    setOpenMenuId(null);
    var note = findNote(noteId);
    if (note) {
      setViewModal({ isOpen: true, note: note });
    }
  }

  function handleEditNote(noteId) {
    setOpenMenuId(null);
    var note = findNote(noteId);
    if (note) {
      // Close view modal if open
      setViewModal({ isOpen: false, note: null });
      setNoteModal({ isOpen: true, editNote: note, sectionId: null });
    }
  }

  function handleDeleteNote(noteId) {
    setOpenMenuId(null);
    if (!confirm('Delete this note?')) return;

    showToast('Deleting\u2026', 'loading');
    fetch(urls.deleteNote.replace('0', noteId), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success) {
          setSections(function (prev) {
            return prev.map(function (s) {
              return { ...s, notes: s.notes.filter(function (n) { return n.id !== noteId; }) };
            });
          });
          setInboxNotes(function (prev) {
            return prev.filter(function (n) { return n.id !== noteId; });
          });
          showToast('Note deleted', 'success');
        } else {
          alert('Error deleting note: ' + (data.error || 'Unknown error'));
        }
      })
      .catch(function (err) {
        alert('Error deleting note');
        console.error(err);
      });
  }

  function handleSaveNote(data) {
    var isEdit = data.id !== undefined;
    var url = isEdit
      ? urls.updateNote.replace('0', data.id)
      : urls.createNote;

    showToast('Saving\u2026', 'loading');
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: data.title,
        content: data.content,
        section_id: data.sectionId,
        source_reference: data.sourceUrl,
        source_title: data.sourceTitle,
        tags: data.tags,
      }),
    })
      .then(function (response) {
        return response.text().then(function (rawText) {
          var parsed;
          try {
            parsed = rawText ? JSON.parse(rawText) : {};
          } catch (e) {
            throw new Error('Server returned invalid response (status ' + response.status + ')');
          }
          return parsed;
        });
      })
      .then(function (result) {
        if (result.success) {
          setNoteModal({ isOpen: false, editNote: null, sectionId: null });

          var noteData = {
            id: (result.note && result.note.id) || data.id,
            title: data.title,
            content: data.content,
            contentHtml: blocknoteToPreviewHtml(data.content),
            sourceUrl: data.sourceUrl || '',
            sourceTitle: data.sourceTitle || '',
            tags: data.tags || '',
            noteType: 'note',
            sectionId: data.sectionId,
          };

          if (isEdit) {
            // Update in sections
            setSections(function (prev) {
              return prev.map(function (s) {
                return {
                  ...s,
                  notes: s.notes.map(function (n) {
                    return n.id === data.id ? { ...n, ...noteData } : n;
                  }),
                };
              });
            });
            // Update in inbox
            setInboxNotes(function (prev) {
              return prev.map(function (n) {
                return n.id === data.id ? { ...n, ...noteData } : n;
              });
            });

            // Check if section changed — need to move
            var oldNote = findNote(data.id);
            if (oldNote && String(oldNote.sectionId || '') !== String(data.sectionId || '')) {
              moveNoteInState(data.id, data.sectionId);
            }

            showToast('Note updated', 'success');
          } else {
            // Insert new note
            if (data.sectionId) {
              setSections(function (prev) {
                return prev.map(function (s) {
                  if (String(s.id) === String(data.sectionId)) {
                    return { ...s, notes: [...s.notes, noteData] };
                  }
                  return s;
                });
              });
            } else {
              setInboxNotes(function (prev) { return [...prev, noteData]; });
            }
            showToast('Note created', 'success');
          }

          // Trigger company detection (non-blocking)
          if (typeof window.detectAndSuggestCompanies === 'function') {
            var combinedText = data.title + ' ' + data.content;
            window.detectAndSuggestCompanies(combinedText, 'note', noteData.id, function () {});
          }
        } else {
          alert('Error saving note: ' + (result.error || result.message || 'Unknown error'));
        }
      })
      .catch(function (err) {
        console.error('saveNote failed:', err);
        alert('Error saving note: ' + (err.message || 'Network or server error'));
      });
  }

  function handleQuickNote() {
    var noteTitle = prompt('Note title:');
    if (!noteTitle || !noteTitle.trim()) return;
    var noteContent = prompt('Note content:');
    if (!noteContent || !noteContent.trim()) return;

    showToast('Saving\u2026', 'loading');
    fetch(urls.createNote, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: noteTitle.trim(),
        content: noteContent.trim(),
        section_id: null,
      }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success) {
          showToast('Quick note created', 'success');
        } else {
          alert('Error creating note: ' + (data.error || 'Unknown error'));
        }
      })
      .catch(function () { alert('Error creating note'); });
  }

  // -----------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------

  var isEmpty = sections.length === 0 && inboxNotes.length === 0;

  return (
    <div className="atomic-canvas-container">
      {/* Canvas Toolbar */}
      <div className="canvas-toolbar">
        <button
          className="btn btn-primary btn-sm"
          onClick={function () { setNoteModal({ isOpen: true, editNote: null, sectionId: null }); }}
        >
          <i className="bi bi-plus-lg" /> New Note
        </button>
        <button
          className="btn btn-outline-secondary btn-sm"
          onClick={function () { setSectionModal({ isOpen: true, editSection: null }); }}
        >
          <i className="bi bi-layout-wtf" /> New Section
        </button>
        <div className="canvas-toolbar-spacer" />
        <div className="canvas-view-options">
          <small className="text-muted">Notes are auto-saved</small>
        </div>
      </div>

      {/* Notes Canvas */}
      <div className="notes-canvas" id="notesCanvas">
        {/* Inbox */}
        {inboxNotes.length > 0 && (
          <CanvasSection
            section={{ id: null, title: 'Inbox', icon: '\u{1F4E5}', description: null, notes: inboxNotes }}
            isInbox={true}
            expandedNotes={expandedNotes}
            openMenuId={openMenuId}
            dragOverSectionId={dragOverSectionId}
            onAddNote={function () {}}
            onEditSection={function () {}}
            onDeleteSection={function () {}}
            onToggleExpand={handleToggleExpand}
            onToggleMenu={handleToggleMenu}
            onViewNote={handleViewNote}
            onEditNote={handleEditNote}
            onDeleteNote={handleDeleteNote}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            onDragLeave={handleDragLeave}
          />
        )}

        {/* Empty State */}
        {isEmpty && (
          <div className="canvas-empty-state" id="canvasEmptyState">
            <i className="bi bi-kanban" style={{ fontSize: '3rem', color: '#d1d5db' }} />
            <h3 className="text-muted">Your Research Canvas</h3>
            <p className="text-muted">Start by creating a section to organize your notes</p>
            <button
              className="btn btn-primary mt-3"
              onClick={function () { setSectionModal({ isOpen: true, editSection: null }); }}
            >
              <i className="bi bi-plus-circle" /> Create First Section
            </button>
          </div>
        )}

        {/* Sections */}
        {sections.map(function (section) {
          return (
            <CanvasSection
              key={section.id}
              section={section}
              isInbox={false}
              expandedNotes={expandedNotes}
              openMenuId={openMenuId}
              dragOverSectionId={dragOverSectionId}
              onAddNote={function (sectionId) {
                setNoteModal({ isOpen: true, editNote: null, sectionId: sectionId });
              }}
              onEditSection={function (s) {
                setSectionModal({ isOpen: true, editSection: s });
              }}
              onDeleteSection={handleDeleteSection}
              onToggleExpand={handleToggleExpand}
              onToggleMenu={handleToggleMenu}
              onViewNote={handleViewNote}
              onEditNote={handleEditNote}
              onDeleteNote={handleDeleteNote}
              onDragStart={handleDragStart}
              onDragEnd={handleDragEnd}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onDragLeave={handleDragLeave}
            />
          );
        })}
      </div>

      {/* Modals */}
      <SectionModal
        isOpen={sectionModal.isOpen}
        editSection={sectionModal.editSection}
        onSave={handleSaveSection}
        onClose={function () { setSectionModal({ isOpen: false, editSection: null }); }}
      />
      <NoteModal
        isOpen={noteModal.isOpen}
        editNote={noteModal.editNote}
        sectionId={noteModal.sectionId}
        onSave={handleSaveNote}
        onClose={function () { setNoteModal({ isOpen: false, editNote: null, sectionId: null }); }}
      />
      <ViewNoteModal
        isOpen={viewModal.isOpen}
        note={viewModal.note}
        onEdit={handleEditNote}
        onClose={function () { setViewModal({ isOpen: false, note: null }); }}
      />
    </div>
  );
}
