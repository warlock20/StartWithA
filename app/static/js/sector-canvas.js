/**
 * Sector Research Canvas - Atomic Notes Management
 * Handles sections, notes, drag-and-drop, and note viewing/editing
 */

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
            location.reload();
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
            location.reload();
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
            location.reload();
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
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Detect company mentions in the note content
            const savedNoteId = (data.note && data.note.id) || noteId;
            const combinedText = title + ' ' + textContent;

            // Close the note modal first
            const noteModalElement = document.getElementById('noteModal');
            const noteModal = bootstrap.Modal.getInstance(noteModalElement);
            if (noteModal) {
                noteModal.hide();
            }

            // Trigger company detection (function from company-tagging.js)
            if (typeof detectAndSuggestCompanies === 'function') {
                detectAndSuggestCompanies(combinedText, 'note', savedNoteId, function() {
                    // Reload page after company tagging is complete (or skipped)
                    location.reload();
                });
            } else {
                // If company tagging not available, just reload
                location.reload();
            }
        } else {
            alert('Error saving note: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(err => {
        alert('Error saving note');
        console.error(err);
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
            location.reload();
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
            // Reload page to show updated organization
            location.reload();
        } else {
            alert('Error moving note: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(err => {
        console.error('Error:', err);
        alert('Error moving note');
    });
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
