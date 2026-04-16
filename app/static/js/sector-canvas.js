/**
 * Sector Research Canvas - Atomic Notes Management
 * Handles sections, notes, drag-and-drop, and note viewing/editing
 */

// ==================== DOM HELPERS ====================

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function blocknoteToPreviewHtml(contentJson) {
    try {
        const blocks = JSON.parse(contentJson);
        if (!Array.isArray(blocks)) return escapeHtml(contentJson);
        return blocks.map(block => {
            if (block.content && Array.isArray(block.content)) {
                const text = block.content
                    .filter(item => item && item.type === 'text')
                    .map(item => item.text || '')
                    .join('');
                if (!text) return '';
                const tag = block.type === 'heading' ? 'h3' : 'p';
                return `<${tag}>${escapeHtml(text)}</${tag}>`;
            }
            return '';
        }).filter(Boolean).join('');
    } catch (e) {
        return escapeHtml(contentJson);
    }
}

function buildSectionHtml(section) {
    const iconHtml = section.icon
        ? `<span class="canvas-section-icon">${escapeHtml(section.icon)}</span>`
        : '';
    const descHtml = section.description
        ? `<div class="canvas-section-description">${escapeHtml(section.description)}</div>`
        : '';
    const escapedTitle = escapeHtml(section.title);
    const escapedDesc = escapeHtml(section.description || '');

    return `
        <div class="canvas-section" data-section-id="${section.id}">
            <div class="canvas-section-header">
                <div class="canvas-section-title">
                    ${iconHtml}
                    <h2>${escapedTitle}</h2>
                </div>
                <div class="canvas-section-actions">
                    <button class="btn btn-sm btn-outline-primary" onclick="addNoteToSection(${section.id})">
                        <i class="bi bi-plus"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-secondary" onclick="editSection(${section.id}, '${escapedTitle.replace(/'/g, "\\'")}', '${escapedDesc.replace(/'/g, "\\'")}')">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteSection(${section.id})">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </div>
            ${descHtml}
            <div class="note-cards-grid" data-section-id="${section.id}">
                <button class="add-note-btn" onclick="addNoteToSection(${section.id})">
                    <i class="bi bi-plus-circle"></i> Add First Note
                </button>
            </div>
        </div>`;
}

function buildNoteCardHtml(note) {
    const previewHtml = blocknoteToPreviewHtml(note.content);
    const escapedContent = escapeHtml(note.content);
    const sourceHtml = note.source_reference
        ? `<a href="${escapeHtml(note.source_reference)}" target="_blank" class="note-card-source"><i class="bi bi-box-arrow-up-right"></i> Source</a>`
        : '';
    const tagsHtml = note.tags
        ? `<div class="note-card-tags">${note.tags.split(',').map(t => `<span class="note-card-tag">${escapeHtml(t.trim())}</span>`).join('')}</div>`
        : '';

    return `
        <div class="note-card" draggable="true"
             data-note-id="${note.id}"
             data-note-title="${escapeHtml(note.title)}"
             data-note-content="${escapedContent}"
             data-note-content-html="${escapeHtml(previewHtml)}"
             data-note-source-url="${escapeHtml(note.source_reference || '')}"
             data-note-source-title="${escapeHtml(note.source_title || '')}"
             data-note-tags="${escapeHtml(note.tags || '')}"
             data-section-id="${note.section_id || ''}">
            <div class="note-card-header">
                <h3 class="note-card-title">${escapeHtml(note.title)}</h3>
                <div class="note-card-menu-wrapper">
                    <button class="note-card-menu-btn" onclick="toggleNoteMenu(${note.id})">
                        <i class="bi bi-three-dots-vertical"></i>
                    </button>
                    <div class="note-card-dropdown" id="noteMenu${note.id}" style="display: none;">
                        <button onclick="viewNote(${note.id})">
                            <i class="bi bi-eye"></i> View Full Note
                        </button>
                        <button onclick="editNote(${note.id})">
                            <i class="bi bi-pencil"></i> Edit
                        </button>
                        <button onclick="deleteNote(${note.id})" class="text-danger">
                            <i class="bi bi-trash"></i> Delete
                        </button>
                    </div>
                </div>
            </div>
            <div class="note-card-content">${previewHtml}</div>
            <div class="note-card-footer">
                <div class="note-card-type">
                    <i class="bi bi-pencil"></i> Note
                </div>
                ${sourceHtml}
            </div>
            ${tagsHtml}
        </div>`;
}

function updateCanvasEmptyState() {
    const canvas = document.getElementById('notesCanvas');
    if (!canvas) return;
    const sections = canvas.querySelectorAll('.canvas-section');
    const emptyState = document.getElementById('canvasEmptyState');

    if (sections.length === 0) {
        if (!emptyState) {
            canvas.innerHTML = `
                <div class="canvas-empty-state" id="canvasEmptyState">
                    <i class="bi bi-kanban" style="font-size: 3rem; color: #d1d5db;"></i>
                    <h3 class="text-muted">Your Research Canvas</h3>
                    <p class="text-muted">Start by creating a section to organize your notes</p>
                    <button class="btn btn-primary mt-3" onclick="createNewSection()">
                        <i class="bi bi-plus-circle"></i> Create First Section
                    </button>
                </div>`;
        }
    } else if (emptyState) {
        emptyState.remove();
    }
}

function initDragDropOnNew(container) {
    container.querySelectorAll('.note-card, .collector-item').forEach(item => {
        item.addEventListener('dragstart', handleDragStart);
        item.addEventListener('dragend', handleDragEnd);
    });
    container.querySelectorAll('.canvas-section, .collector-items').forEach(section => {
        section.addEventListener('dragover', handleDragOver);
        section.addEventListener('drop', handleDrop);
        section.addEventListener('dragleave', handleDragLeave);
    });
    container.querySelectorAll('.note-cards-grid').forEach(grid => {
        grid.addEventListener('dragover', handleDragOver);
        grid.addEventListener('drop', handleDrop);
        grid.addEventListener('dragleave', handleDragLeave);
    });
    // Also init expand behavior on new note cards
    container.querySelectorAll('.note-card').forEach(card => {
        card.addEventListener('click', function(e) {
            if (e.target.closest('.note-card-menu-wrapper') || e.target.closest('.note-card-dropdown')) return;
            if (this.classList.contains('dragging')) return;
            this.classList.toggle('expanded');
        });
    });
}

function closeModal(modalId) {
    const el = document.getElementById(modalId);
    if (!el) return;
    const instance = bootstrap.Modal.getInstance(el);
    if (instance) instance.hide();
}

// ==================== SECTION MANAGEMENT ====================

function createNewSection() {
    // Reset form
    document.getElementById('sectionId').value = '';
    document.getElementById('sectionTitle').value = '';
    document.getElementById('sectionDescription').value = '';
    document.getElementById('sectionIcon').value = '';
    document.getElementById('sectionModalTitle').textContent = 'Create New Section';
    document.getElementById('sectionSaveBtn').textContent = 'Create Section';

    const modal = new bootstrap.Modal(document.getElementById('sectionModal'));
    modal.show();
}

function editSection(sectionId, title, description) {
    document.getElementById('sectionId').value = sectionId;
    document.getElementById('sectionTitle').value = title || '';
    document.getElementById('sectionDescription').value = description || '';
    document.getElementById('sectionIcon').value = '';
    document.getElementById('sectionModalTitle').textContent = 'Edit Section';
    document.getElementById('sectionSaveBtn').textContent = 'Update Section';

    const modal = new bootstrap.Modal(document.getElementById('sectionModal'));
    modal.show();
}

function saveSection() {
    const sectionId = document.getElementById('sectionId').value;
    const title = document.getElementById('sectionTitle').value.trim();
    const description = document.getElementById('sectionDescription').value.trim();
    const icon = document.getElementById('sectionIcon').value.trim();

    if (!title) {
        alert('Please enter a section title');
        return;
    }

    const isEdit = sectionId !== '';
    const url = isEdit
        ? window.sectorUrls.updateSection.replace('0', sectionId)
        : window.sectorUrls.createSection;

    fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            title: title,
            description: description || null,
            icon: icon || null
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            closeModal('sectionModal');

            if (isEdit) {
                // Update existing section in DOM
                const sectionEl = document.querySelector(`.canvas-section[data-section-id="${sectionId}"]`);
                if (sectionEl) {
                    const titleEl = sectionEl.querySelector('.canvas-section-title h2');
                    if (titleEl) titleEl.textContent = title;

                    const iconEl = sectionEl.querySelector('.canvas-section-icon');
                    if (icon) {
                        if (iconEl) {
                            iconEl.textContent = icon;
                        } else {
                            const titleDiv = sectionEl.querySelector('.canvas-section-title');
                            titleDiv.insertAdjacentHTML('afterbegin', `<span class="canvas-section-icon">${escapeHtml(icon)}</span>`);
                        }
                    } else if (iconEl) {
                        iconEl.remove();
                    }

                    let descEl = sectionEl.querySelector('.canvas-section-description');
                    if (description) {
                        if (descEl) {
                            descEl.textContent = description;
                        } else {
                            sectionEl.querySelector('.canvas-section-header').insertAdjacentHTML('afterend',
                                `<div class="canvas-section-description">${escapeHtml(description)}</div>`);
                        }
                    } else if (descEl) {
                        descEl.remove();
                    }

                    // Update the edit button's onclick with new values
                    const editBtn = sectionEl.querySelector('.canvas-section-actions .btn-outline-secondary');
                    if (editBtn) {
                        editBtn.setAttribute('onclick',
                            `editSection(${sectionId}, '${escapeHtml(title).replace(/'/g, "\\'")}', '${escapeHtml(description || '').replace(/'/g, "\\'")}')`);
                    }
                }
                showToast('Section updated', 'success');
            } else {
                // Insert new section into the canvas
                const section = data.section;
                section.icon = icon || null;
                section.description = description || null;
                const html = buildSectionHtml(section);

                const canvas = document.getElementById('notesCanvas');
                canvas.insertAdjacentHTML('beforeend', html);

                // Initialize drag-and-drop on the new section
                const newSectionEl = canvas.querySelector(`.canvas-section[data-section-id="${section.id}"]`);
                if (newSectionEl) initDragDropOnNew(newSectionEl);

                updateCanvasEmptyState();
                showToast('Section created', 'success');
            }
        } else {
            alert('Error saving section: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(err => {
        alert('Error saving section');
        console.error(err);
    });
}

function deleteSection(sectionId) {
    if (!confirm('Delete this section? All notes will be moved to the Collector.')) {
        return;
    }

    fetch(window.sectorUrls.deleteSection.replace('0', sectionId), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const sectionEl = document.querySelector(`.canvas-section[data-section-id="${sectionId}"]`);
            if (sectionEl) {
                sectionEl.style.transition = 'opacity 0.25s, transform 0.25s';
                sectionEl.style.opacity = '0';
                sectionEl.style.transform = 'translateY(-10px)';
                setTimeout(() => {
                    sectionEl.remove();
                    updateCanvasEmptyState();
                }, 250);
            }
            showToast('Section deleted', 'success');
        } else {
            alert('Error deleting section: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(err => {
        alert('Error deleting section');
        console.error(err);
    });
}

// ==================== NOTE MANAGEMENT ====================

function createNewNote() {
    // Reset form fields
    document.getElementById('noteId').value = '';
    document.getElementById('noteSectionId').value = '';
    document.getElementById('noteTitle').value = '';
    document.getElementById('noteSourceUrl').value = '';
    document.getElementById('noteSourceTitle').value = '';
    document.getElementById('noteTags').value = '';
    document.getElementById('noteModalTitle').textContent = 'Create Note (will go to Collector)';
    document.getElementById('noteSaveBtn').textContent = 'Create Note';

    // Open modal - editor will be initialized fresh in sector-document-init.js
    const modal = new bootstrap.Modal(document.getElementById('noteModal'));
    modal.show();
}

function addNoteToSection(sectionId) {
    // Reset form fields
    document.getElementById('noteId').value = '';
    document.getElementById('noteSectionId').value = sectionId;
    document.getElementById('noteTitle').value = '';
    document.getElementById('noteSourceUrl').value = '';
    document.getElementById('noteSourceTitle').value = '';
    document.getElementById('noteTags').value = '';
    document.getElementById('noteModalTitle').textContent = 'Add Note to Section';
    document.getElementById('noteSaveBtn').textContent = 'Create Note';

    // Open modal - editor will be initialized fresh in sector-document-init.js
    const modal = new bootstrap.Modal(document.getElementById('noteModal'));
    modal.show();
}

function createQuickNote() {
    const title = prompt('Note title:');
    if (!title || title.trim() === '') return;

    const content = prompt('Note content:');
    if (!content || content.trim() === '') return;

    fetch(window.sectorUrls.createNote, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            title: title.trim(),
            content: content.trim(),
            section_id: null
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Quick note created', 'success');
            // Quick notes go to collector (no section) — not visible on canvas sections
            // but we still avoid a reload
        } else {
            alert('Error creating note: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(err => {
        alert('Error creating note');
        console.error(err);
    });
}

function saveNote() {
    const noteId = document.getElementById('noteId').value;
    const sectionId = document.getElementById('noteSectionId').value || null;
    const title = document.getElementById('noteTitle').value.trim();

    // Check if editor is initialized
    if (!window.noteEditorInstance || !window.noteEditorInstance.editor) {
        alert('Editor is not ready. Please wait a moment and try again.');
        console.error('BlockNote editor not initialized');
        return;
    }

    // Get content from BlockNote editor
    let content = '';
    let textContent = '';
    if (window.noteEditorInstance && window.noteEditorInstance.editor) {
        const blocks = window.noteEditorInstance.editor.document;
        content = JSON.stringify(blocks);
        // Get plain text for validation - filter for text-type items only
        textContent = blocks.map(block => {
            if (block.content && Array.isArray(block.content)) {
                return block.content
                    .filter(item => item && item.type === 'text')
                    .map(item => item.text || '')
                    .join('');
            }
            return '';
        }).join(' ').trim();
    }

    const sourceUrl = document.getElementById('noteSourceUrl').value.trim();
    const sourceTitle = document.getElementById('noteSourceTitle').value.trim();
    const tags = document.getElementById('noteTags').value.trim();

    // Check if content is empty
    if (!title || !textContent) {
        // Debug logging to help diagnose issues
        console.log('=== Validation Failed ===');
        console.log('Title:', title);
        console.log('Has title:', !!title);
        console.log('TextContent:', textContent);
        console.log('TextContent length:', textContent.length);
        console.log('Has editor:', !!window.noteEditorInstance);
        console.log('Has editor.document:', !!(window.noteEditorInstance && window.noteEditorInstance.editor && window.noteEditorInstance.editor.document));

        if (window.noteEditorInstance && window.noteEditorInstance.editor) {
            const blocks = window.noteEditorInstance.editor.document;
            console.log('Blocks length:', blocks.length);
            console.log('Raw blocks:', JSON.stringify(blocks, null, 2));
        }

        if (!title) {
            alert('Please enter a title for the note');
        } else {
            alert('Please enter content for the note');
        }
        return;
    }

    const isEdit = noteId !== '';
    const url = isEdit
        ? window.sectorUrls.updateNote.replace('0', noteId)
        : window.sectorUrls.createNote;

    fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            title: title,
            content: content,
            section_id: sectionId,
            source_reference: sourceUrl || null,
            source_title: sourceTitle || null,
            tags: tags || null
        })
    })
    .then(async response => {
        // Capture text first so we can show useful errors if response isn't JSON
        const rawText = await response.text();
        let data;
        try {
            data = rawText ? JSON.parse(rawText) : {};
        } catch (parseErr) {
            console.error('Non-JSON response from server (status ' + response.status + '):', rawText);
            throw new Error('Server returned invalid response (status ' + response.status + ')');
        }
        if (!response.ok && !data.error && !data.message) {
            throw new Error('Server error (status ' + response.status + ')');
        }
        return data;
    })
    .then(data => {
        if (data.success) {
            const savedNoteId = (data.note && data.note.id) || noteId;
            const combinedText = title + ' ' + textContent;

            // Close the note modal first
            closeModal('noteModal');

            if (isEdit) {
                // Update existing note card in DOM
                const noteCard = document.querySelector(`.note-card[data-note-id="${noteId}"]`);
                if (noteCard) {
                    noteCard.dataset.noteTitle = title;
                    noteCard.dataset.noteContent = content;
                    noteCard.dataset.noteContentHtml = blocknoteToPreviewHtml(content);
                    noteCard.dataset.noteSourceUrl = sourceUrl || '';
                    noteCard.dataset.noteSourceTitle = sourceTitle || '';
                    noteCard.dataset.noteTags = tags || '';
                    noteCard.dataset.sectionId = sectionId || '';

                    const titleEl = noteCard.querySelector('.note-card-title');
                    if (titleEl) titleEl.textContent = title;

                    const contentEl = noteCard.querySelector('.note-card-content');
                    if (contentEl) contentEl.innerHTML = blocknoteToPreviewHtml(content);

                    // Update source link
                    let sourceEl = noteCard.querySelector('.note-card-source');
                    if (sourceUrl) {
                        if (!sourceEl) {
                            const footer = noteCard.querySelector('.note-card-footer');
                            if (footer) footer.insertAdjacentHTML('beforeend',
                                `<a href="${escapeHtml(sourceUrl)}" target="_blank" class="note-card-source"><i class="bi bi-box-arrow-up-right"></i> Source</a>`);
                        } else {
                            sourceEl.href = sourceUrl;
                        }
                    } else if (sourceEl) {
                        sourceEl.remove();
                    }

                    // Update tags
                    let tagsEl = noteCard.querySelector('.note-card-tags');
                    if (tags) {
                        const tagsHtml = tags.split(',').map(t => `<span class="note-card-tag">${escapeHtml(t.trim())}</span>`).join('');
                        if (tagsEl) {
                            tagsEl.innerHTML = tagsHtml;
                        } else {
                            noteCard.insertAdjacentHTML('beforeend', `<div class="note-card-tags">${tagsHtml}</div>`);
                        }
                    } else if (tagsEl) {
                        tagsEl.remove();
                    }

                    // Move card to new section if section changed
                    const currentSectionId = noteCard.closest('.note-cards-grid')?.dataset.sectionId || '';
                    if (String(sectionId || '') !== String(currentSectionId)) {
                        moveNoteCardInDom(noteCard, sectionId);
                    }
                }
                showToast('Note updated', 'success');
            } else {
                // Insert new note card into the target section
                const noteData = {
                    id: savedNoteId,
                    title: title,
                    content: content,
                    note_type: 'note',
                    section_id: sectionId,
                    source_reference: sourceUrl || null,
                    source_title: sourceTitle || null,
                    tags: tags || null
                };
                const html = buildNoteCardHtml(noteData);

                if (sectionId) {
                    const grid = document.querySelector(`.note-cards-grid[data-section-id="${sectionId}"]`);
                    if (grid) {
                        // Remove "Add First Note" button if present
                        const addBtn = grid.querySelector('.add-note-btn');
                        if (addBtn) addBtn.remove();
                        grid.insertAdjacentHTML('beforeend', html);
                        const newCard = grid.querySelector(`.note-card[data-note-id="${savedNoteId}"]`);
                        if (newCard) initDragDropOnNew(newCard.parentElement);
                    }
                }
                showToast('Note created', 'success');
            }

            // Trigger company detection (non-blocking, no reload)
            if (typeof detectAndSuggestCompanies === 'function') {
                detectAndSuggestCompanies(combinedText, 'note', savedNoteId, function() {
                    // Company tagging complete — no reload needed
                });
            }
        } else {
            alert('Error saving note: ' + (data.error || data.message || 'Unknown error'));
        }
    })
    .catch(err => {
        console.error('saveNote failed:', err);
        alert('Error saving note: ' + (err && err.message ? err.message : 'Network or server error. See browser console for details.'));
    });
}

// ==================== NOTE MENU & VIEWING ====================

let currentViewNoteId = null;

function toggleNoteMenu(noteId) {
    const menu = document.getElementById('noteMenu' + noteId);
    const allMenus = document.querySelectorAll('.note-card-dropdown');

    // Close all other menus
    allMenus.forEach(m => {
        if (m.id !== 'noteMenu' + noteId) {
            m.style.display = 'none';
        }
    });

    // Toggle this menu
    menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
}

// Close menus when clicking outside
document.addEventListener('click', function(e) {
    if (!e.target.closest('.note-card-menu-wrapper')) {
        document.querySelectorAll('.note-card-dropdown').forEach(menu => {
            menu.style.display = 'none';
        });
    }
});

function viewNote(noteId) {
    const noteCard = document.querySelector(`.note-card[data-note-id="${noteId}"]`);

    if (!noteCard) {
        alert('Note not found');
        return;
    }

    currentViewNoteId = noteId;

    // Get note data from data attributes
    const noteTitle = noteCard.dataset.noteTitle;
    const noteContent = noteCard.dataset.noteContent;
    const noteContentHtml = noteCard.dataset.noteContentHtml; // HTML version for display
    const noteSourceUrl = noteCard.dataset.noteSourceUrl;
    const noteSourceTitle = noteCard.dataset.noteSourceTitle;
    const noteTags = noteCard.dataset.noteTags;

    // Set title
    document.getElementById('viewNoteTitle').textContent = noteTitle;

    // Decode and set content (use HTML version if available)
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = noteContentHtml || noteContent;
    document.getElementById('viewNoteContent').innerHTML = tempDiv.innerHTML;

    // Show/hide source
    const sourceWrapper = document.getElementById('viewNoteSourceWrapper');
    if (noteSourceUrl) {
        const sourceLink = document.getElementById('viewNoteSource');
        sourceLink.href = noteSourceUrl;
        sourceLink.textContent = noteSourceTitle || noteSourceUrl;
        sourceWrapper.style.display = 'block';
    } else {
        sourceWrapper.style.display = 'none';
    }

    // Show/hide tags
    const tagsWrapper = document.getElementById('viewNoteTagsWrapper');
    if (noteTags) {
        const tagsContainer = document.getElementById('viewNoteTags');
        const tagsArray = noteTags.split(',');
        tagsContainer.innerHTML = tagsArray.map(tag =>
            `<span class="note-card-tag">${tag.trim()}</span>`
        ).join(' ');
        tagsWrapper.style.display = 'block';
    } else {
        tagsWrapper.style.display = 'none';
    }

    // Open modal
    const modal = new bootstrap.Modal(document.getElementById('viewNoteModal'));
    modal.show();

    // Close dropdown menu
    document.querySelectorAll('.note-card-dropdown').forEach(menu => {
        menu.style.display = 'none';
    });
}

function editNoteFromView() {
    if (currentViewNoteId) {
        // Close view modal
        const viewModal = bootstrap.Modal.getInstance(document.getElementById('viewNoteModal'));
        viewModal.hide();

        // Open edit modal
        editNote(currentViewNoteId);
    }
}

function editNote(noteId) {
    const noteCard = document.querySelector(`.note-card[data-note-id="${noteId}"]`);

    if (!noteCard) {
        alert('Note not found');
        return;
    }

    // Get note data from data attributes
    const noteTitle = noteCard.dataset.noteTitle;
    const noteContent = noteCard.dataset.noteContent;
    const noteSourceUrl = noteCard.dataset.noteSourceUrl;
    const noteSourceTitle = noteCard.dataset.noteSourceTitle;
    const noteTags = noteCard.dataset.noteTags;
    const sectionId = noteCard.dataset.sectionId;

    // Populate form fields
    document.getElementById('noteId').value = noteId;
    document.getElementById('noteSectionId').value = sectionId;
    document.getElementById('noteTitle').value = noteTitle;
    document.getElementById('noteSourceUrl').value = noteSourceUrl;
    document.getElementById('noteSourceTitle').value = noteSourceTitle;
    document.getElementById('noteTags').value = noteTags;

    // Update modal title and button
    document.getElementById('noteModalTitle').textContent = 'Edit Note';
    document.getElementById('noteSaveBtn').textContent = 'Update Note';

    // Open modal
    const modal = new bootstrap.Modal(document.getElementById('noteModal'));
    modal.show();

    // Set BlockNote content after modal is shown and editor is initialized
    // Wait for editor to be ready (it's initialized in sector-document-init.js)
    const setContentWhenReady = () => {
        setTimeout(() => {
            if (window.noteEditorInstance && window.noteEditorInstance.editor) {
                // Decode HTML entities first
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = noteContent;
                const decodedContent = tempDiv.innerHTML;

                // Try to parse as JSON (BlockNote format) first
                try {
                    const blocks = JSON.parse(decodedContent);
                    if (Array.isArray(blocks)) {
                        window.noteEditorInstance.editor.replaceBlocks(
                            window.noteEditorInstance.editor.document,
                            blocks
                        );
                    }
                } catch (e) {
                    // Not JSON - it's HTML, use insertHTML method
                    if (window.noteEditorInstance.insertHTML) {
                        // Clear first
                        window.noteEditorInstance.editor.replaceBlocks(
                            window.noteEditorInstance.editor.document,
                            [{ type: "paragraph", content: [] }]
                        );
                        // Then insert HTML
                        window.noteEditorInstance.insertHTML(decodedContent);
                    }
                }
            } else {
                // Editor not ready yet, try again
                console.warn('Editor not ready, retrying...');
                setContentWhenReady();
            }
        }, 200);
    };

    document.getElementById('noteModal').addEventListener('shown.bs.modal', setContentWhenReady, { once: true });

    // Close dropdown menu
    document.querySelectorAll('.note-card-dropdown').forEach(menu => {
        menu.style.display = 'none';
    });
}

function deleteNote(noteId) {
    if (!confirm('Delete this note?')) {
        return;
    }

    fetch(window.sectorUrls.deleteNote.replace('0', noteId), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const noteCard = document.querySelector(`.note-card[data-note-id="${noteId}"]`);
            if (noteCard) {
                const grid = noteCard.closest('.note-cards-grid');
                noteCard.style.transition = 'opacity 0.25s, transform 0.25s';
                noteCard.style.opacity = '0';
                noteCard.style.transform = 'scale(0.95)';
                setTimeout(() => {
                    noteCard.remove();
                    // If grid is now empty, show "Add First Note" button
                    if (grid && !grid.querySelector('.note-card')) {
                        const sectionId = grid.dataset.sectionId;
                        if (sectionId && !grid.querySelector('.add-note-btn')) {
                            grid.innerHTML = `<button class="add-note-btn" onclick="addNoteToSection(${sectionId})">
                                <i class="bi bi-plus-circle"></i> Add First Note
                            </button>`;
                        }
                    }
                }, 250);
            }
            // Close any open dropdown menus
            document.querySelectorAll('.note-card-dropdown').forEach(menu => {
                menu.style.display = 'none';
            });
            showToast('Note deleted', 'success');
        } else {
            alert('Error deleting note: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(err => {
        alert('Error deleting note');
        console.error(err);
    });
}

// ==================== DRAG AND DROP ====================

let draggedNoteId = null;
let draggedElement = null;

function initializeDragAndDrop() {
    // Make all note cards and collector items draggable
    document.querySelectorAll('.note-card, .collector-item').forEach(item => {
        item.addEventListener('dragstart', handleDragStart);
        item.addEventListener('dragend', handleDragEnd);
    });

    // Make sections drop zones
    document.querySelectorAll('.canvas-section, .collector-items').forEach(section => {
        section.addEventListener('dragover', handleDragOver);
        section.addEventListener('drop', handleDrop);
        section.addEventListener('dragleave', handleDragLeave);
    });

    // Also make note-cards-grid drop zones
    document.querySelectorAll('.note-cards-grid').forEach(grid => {
        grid.addEventListener('dragover', handleDragOver);
        grid.addEventListener('drop', handleDrop);
        grid.addEventListener('dragleave', handleDragLeave);
    });
}

function handleDragStart(e) {
    draggedElement = this;
    draggedNoteId = this.dataset.noteId;

    this.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', this.innerHTML);
}

function handleDragEnd(e) {
    this.classList.remove('dragging');

    // Remove all drop zone highlights
    document.querySelectorAll('.drop-zone-active').forEach(el => {
        el.classList.remove('drop-zone-active');
    });
}

function handleDragOver(e) {
    if (e.preventDefault) {
        e.preventDefault(); // Allows us to drop
    }

    e.dataTransfer.dropEffect = 'move';

    // Add visual feedback
    if (this.classList.contains('canvas-section') ||
        this.classList.contains('note-cards-grid') ||
        this.classList.contains('collector-items')) {
        this.classList.add('drop-zone-active');
    }

    return false;
}

function handleDragLeave(e) {
    this.classList.remove('drop-zone-active');
}

function handleDrop(e) {
    if (e.stopPropagation) {
        e.stopPropagation(); // Stops browser from redirecting
    }

    this.classList.remove('drop-zone-active');

    if (!draggedNoteId) return false;

    // Determine the target section
    let targetSectionId = null;
    let targetElement = e.target;

    // If dropped in collector
    if (targetElement.classList.contains('collector-items') ||
        targetElement.closest('.collector-items')) {
        targetSectionId = null; // null means collector
    }
    // If dropped in a section
    else if (targetElement.classList.contains('note-cards-grid')) {
        const section = targetElement.closest('.canvas-section');
        if (section) {
            targetSectionId = section.dataset.sectionId;
        }
    }
    else if (targetElement.classList.contains('canvas-section')) {
        targetSectionId = targetElement.dataset.sectionId;
    }
    else {
        const section = targetElement.closest('.canvas-section');
        if (section) {
            targetSectionId = section.dataset.sectionId;
        }
    }

    // Update note's section via API
    moveNoteToSection(draggedNoteId, targetSectionId);

    return false;
}

function moveNoteToSection(noteId, sectionId) {
    fetch(`/sectors/note/${noteId}/update`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            section_id: sectionId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const noteCard = document.querySelector(`.note-card[data-note-id="${noteId}"]`);
            if (noteCard) {
                moveNoteCardInDom(noteCard, sectionId);
            }
            showToast('Note moved', 'success');
        } else {
            alert('Error moving note: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(err => {
        console.error('Error:', err);
        alert('Error moving note');
    });
}

function moveNoteCardInDom(noteCard, targetSectionId) {
    const sourceGrid = noteCard.closest('.note-cards-grid');

    // Remove from current location
    noteCard.remove();

    // If source grid is now empty, show "Add First Note" button
    if (sourceGrid && !sourceGrid.querySelector('.note-card')) {
        const srcSectionId = sourceGrid.dataset.sectionId;
        if (srcSectionId && !sourceGrid.querySelector('.add-note-btn')) {
            sourceGrid.innerHTML = `<button class="add-note-btn" onclick="addNoteToSection(${srcSectionId})">
                <i class="bi bi-plus-circle"></i> Add First Note
            </button>`;
        }
    }

    // Insert into target section
    if (targetSectionId) {
        const targetGrid = document.querySelector(`.note-cards-grid[data-section-id="${targetSectionId}"]`);
        if (targetGrid) {
            // Remove "Add First Note" button if present
            const addBtn = targetGrid.querySelector('.add-note-btn');
            if (addBtn) addBtn.remove();

            noteCard.dataset.sectionId = targetSectionId;
            targetGrid.appendChild(noteCard);
        }
    }
}

// ==================== NOTE CARD EXPAND/COLLAPSE ====================

function initializeNoteCardExpand() {
    document.querySelectorAll('.note-card').forEach(card => {
        card.addEventListener('click', function(e) {
            // Don't expand if clicking on menu button or dropdown
            if (e.target.closest('.note-card-menu-wrapper') ||
                e.target.closest('.note-card-dropdown')) {
                return;
            }

            // Don't expand if currently dragging
            if (this.classList.contains('dragging')) {
                return;
            }

            // Toggle expanded state
            this.classList.toggle('expanded');
        });
    });
}

// ==================== SCROLL FADE EFFECTS ====================

function initializeScrollFadeEffects() {
    // Track scroll position for research tab content
    const tabContent = document.querySelector('.research-tab-content');
    if (tabContent) {
        tabContent.addEventListener('scroll', function() {
            // Add scrolled class when scrolled down from top
            if (this.scrollTop > 20) {
                this.classList.add('scrolled');
            } else {
                this.classList.remove('scrolled');
            }

            // Add scrolled-bottom class when near bottom
            const isNearBottom = this.scrollHeight - this.scrollTop - this.clientHeight < 20;
            if (isNearBottom) {
                this.classList.add('scrolled-bottom');
            } else {
                this.classList.remove('scrolled-bottom');
            }
        });
    }

    // Track scroll position for sticky sidebar
    const sidebar = document.querySelector('.sticky-sidebar');
    if (sidebar) {
        sidebar.addEventListener('scroll', function() {
            if (this.scrollTop > 20) {
                this.classList.add('scrolled');
            } else {
                this.classList.remove('scrolled');
            }
        });
    }

    // Track scroll position for notes canvas
    const notesCanvas = document.querySelector('.notes-canvas');
    if (notesCanvas) {
        notesCanvas.addEventListener('scroll', function() {
            if (this.scrollTop > 20) {
                this.classList.add('scrolled');
            } else {
                this.classList.remove('scrolled');
            }
        });
    }
}

// ==================== QUICK TOOLS SIDEBAR ====================

function getSectorNameFromUrl() {
    const pathParts = window.location.pathname.split('/');
    return pathParts[pathParts.indexOf('sectors') + 1];
}

function addCompanyToSector(companyId, callback) {
    const sectorName = getSectorNameFromUrl();
    fetch(`/sectors/${sectorName}/add_company/${companyId}`, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            callback(data.company);
        } else {
            showToast(data.error || 'Failed to add company', 'error');
        }
    })
    .catch(() => showToast('Network error', 'error'));
}

function removeCompanyFromSector(companyId, callback) {
    const sectorName = getSectorNameFromUrl();
    fetch(`/sectors/${sectorName}/remove_company/${companyId}`, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            callback(data.company);
        } else {
            showToast(data.error || 'Failed to remove company', 'error');
        }
    })
    .catch(() => showToast('Network error', 'error'));
}

function showToast(message, type) {
    // Use existing flash mechanism or create a simple toast
    const toast = document.createElement('div');
    toast.className = `alert alert-${type === 'error' ? 'danger' : 'success'} alert-dismissible fade show`;
    toast.style.cssText = 'position:fixed;top:1rem;right:1rem;z-index:9999;min-width:250px;box-shadow:0 4px 12px rgba(0,0,0,.15);';
    toast.innerHTML = `${message}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

function updateCompanyBadgeCount() {
    const list = document.getElementById('companiesList');
    const badge = document.querySelector('#companiesCollapse')
        ?.closest('.accordion-item')
        ?.querySelector('.badge');
    if (badge && list) {
        badge.textContent = list.querySelectorAll('.tool-item').length;
    }
}

function appendCompanyToList(company) {
    const list = document.getElementById('companiesList');
    if (!list) return;
    // Remove "No companies tracked" message if present
    const emptyMsg = list.querySelector('p.text-muted');
    if (emptyMsg) emptyMsg.remove();

    const item = document.createElement('div');
    item.className = 'tool-item';
    item.dataset.companyId = company.id;
    item.innerHTML = `
        <div class="tool-item-text">
            <strong>${company.name}</strong>
            <small class="d-block text-muted">${company.ticker}</small>
            ${company.is_in_portfolio ? '<span class="badge bg-info">Portfolio</span>' : ''}
        </div>
        <div class="tool-item-actions">
            <a href="${company.dashboard_url}" class="btn btn-sm btn-link p-0" title="View company">
                <i class="bi bi-eye"></i>
            </a>
            <button type="button" class="btn btn-sm btn-link p-0 text-danger btn-remove-company" data-company-id="${company.id}" data-company-name="${company.name}" title="Remove from sector">
                <i class="bi bi-x-circle"></i>
            </button>
        </div>`;
    list.appendChild(item);
    updateCompanyBadgeCount();
}

function removeCompanyFromList(companyId) {
    const item = document.querySelector(`#companiesList .tool-item[data-company-id="${companyId}"]`);
    if (item) {
        item.style.transition = 'opacity 0.2s, transform 0.2s';
        item.style.opacity = '0';
        item.style.transform = 'translateX(10px)';
        setTimeout(() => {
            item.remove();
            updateCompanyBadgeCount();
            // Show empty message if no companies left
            const list = document.getElementById('companiesList');
            if (list && !list.querySelector('.tool-item')) {
                list.innerHTML = '<p class="text-muted small text-center mb-0">No companies tracked</p>';
            }
        }, 200);
    }
}

function addOptionToSelect(company) {
    const select = document.getElementById('companySelect');
    if (!select) return;
    const opt = document.createElement('option');
    opt.value = company.id;
    opt.textContent = company.name;
    // Insert alphabetically
    const options = Array.from(select.options).slice(1); // skip "Select..."
    const insertBefore = options.find(o => o.textContent.localeCompare(company.name) > 0);
    select.insertBefore(opt, insertBefore || null);
}

function removeOptionFromSelect(companyId) {
    const select = document.getElementById('companySelect');
    if (!select) return;
    const opt = select.querySelector(`option[value="${companyId}"]`);
    if (opt) opt.remove();
    select.value = '';
}

// ==================== INITIALIZATION ====================

document.addEventListener('DOMContentLoaded', function() {
    initializeDragAndDrop();
    initializeNoteCardExpand();
    initializeScrollFadeEffects();

    // Add company form - intercept submit and use fetch
    const addForm = document.getElementById('addCompanyForm');
    if (addForm) {
        addForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const select = document.getElementById('companySelect');
            const companyId = select.value;
            if (!companyId) return;

            const btn = addForm.querySelector('button[type="submit"]');
            btn.disabled = true;
            btn.innerHTML = '<i class="bi bi-hourglass-split"></i>';

            addCompanyToSector(companyId, function(company) {
                appendCompanyToList(company);
                removeOptionFromSelect(companyId);
                showToast(`${company.name} added to sector`, 'success');
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-plus"></i>';
            });
        });
    }

    // Remove company - delegate click events on the list
    const companiesList = document.getElementById('companiesList');
    if (companiesList) {
        companiesList.addEventListener('click', function(e) {
            const btn = e.target.closest('.btn-remove-company');
            if (!btn) return;
            e.preventDefault();

            const companyId = btn.dataset.companyId;
            const companyName = btn.dataset.companyName;
            if (!confirm(`Remove ${companyName} from this sector?`)) return;

            btn.disabled = true;
            removeCompanyFromSector(companyId, function(company) {
                removeCompanyFromList(companyId);
                addOptionToSelect(company);
                showToast(`${company.name} removed from sector`, 'success');
            });
        });
    }

    // Setup New Company button handler
    const newCompanyBtn = document.getElementById('newCompanyBtn');
    if (newCompanyBtn) {
        newCompanyBtn.addEventListener('click', function() {
            if (typeof openCompanyModal === 'function') {
                openCompanyModal(function(company) {
                    addCompanyToSector(company.id, function(added) {
                        appendCompanyToList(added);
                        removeOptionFromSelect(company.id);
                        showToast(`${added.name} added to sector`, 'success');
                    });
                });
            } else {
                console.error('Company search component not loaded');
            }
        });
    }
});
