/**
 * Generate Document from Canvas
 * Handles selecting sections/notes from canvas and inserting into Document View
 */

// Store canvas data
let canvasData = {
    sections: [],
    collectorNotes: []
};

/**
 * Open the generate document modal and populate with sections
 */
async function openGenerateDocumentModal() {
    const modal = new bootstrap.Modal(document.getElementById('generateDocumentModal'));

    try {
        // Check if URL is configured
        if (!window.sectorUrls || !window.sectorUrls.generateDocument) {
            console.error('Sector URLs not configured. window.sectorUrls:', window.sectorUrls);
            showAlert('Configuration error: sector URLs not found', 'error');
            return;
        }

        // Fetch canvas data
        console.log('Fetching from:', window.sectorUrls.generateDocument);
        const response = await fetch(window.sectorUrls.generateDocument);

        if (!response.ok) {
            console.error('HTTP error:', response.status, response.statusText);
            showAlert(`Server error: ${response.status} ${response.statusText}`, 'error');
            return;
        }

        const data = await response.json();
        console.log('Received data:', data);

        if (!data.success) {
            showAlert(data.error || 'Failed to load canvas data', 'error');
            return;
        }

        // Store the data
        canvasData.sections = data.sections || [];
        canvasData.collectorNotes = data.collector_notes || [];

        console.log('Canvas data loaded:', canvasData);

        // Populate the modal
        populateSectionsSelection();

        // Show modal
        modal.show();

    } catch (error) {
        console.error('Error loading canvas data:', error);
        showAlert('Error loading canvas data: ' + error.message, 'error');
    }
}

/**
 * Populate the sections selection list
 */
function populateSectionsSelection() {
    const listContainer = document.getElementById('sectionsSelectionList');
    const noSectionsMsg = document.getElementById('noSectionsMessage');

    // Check if we have any sections or notes
    if (canvasData.sections.length === 0 && canvasData.collectorNotes.length === 0) {
        listContainer.style.display = 'none';
        noSectionsMsg.style.display = 'block';
        return;
    }

    listContainer.style.display = 'block';
    noSectionsMsg.style.display = 'none';
    listContainer.innerHTML = '';

    // Add each section
    canvasData.sections.forEach((section, index) => {
        const sectionItem = createSectionSelectionItem(section, index);
        listContainer.appendChild(sectionItem);
    });

    // Add collector if it has notes
    if (canvasData.collectorNotes.length > 0) {
        const collectorSection = {
            id: 'collector',
            title: 'Collector (Unorganized Notes)',
            icon: '📥',
            description: 'Notes not yet organized into sections',
            notes_count: canvasData.collectorNotes.length
        };
        const collectorItem = createSectionSelectionItem(collectorSection, 'collector');
        listContainer.appendChild(collectorItem);
    }
}

/**
 * Create a section selection checkbox item
 */
function createSectionSelectionItem(section, index) {
    const div = document.createElement('div');
    div.className = 'section-selection-item selected';
    div.dataset.sectionIndex = index;

    const icon = section.icon || '📌';
    const notesCount = section.notes_count || 0;

    div.innerHTML = `
        <div class="section-selection-header" onclick="toggleSectionSelection(${index})">
            <input type="checkbox"
                   class="section-selection-checkbox"
                   id="section-${index}"
                   checked
                   onclick="event.stopPropagation(); toggleSectionSelection(${index})">
            <span class="section-icon">${icon}</span>
            <div class="section-info">
                <div class="section-title">${section.title}</div>
                ${section.description ? `<div class="section-description">${section.description}</div>` : ''}
            </div>
            <span class="section-notes-count">${notesCount} ${notesCount === 1 ? 'note' : 'notes'}</span>
        </div>
    `;

    return div;
}

/**
 * Toggle section selection
 */
function toggleSectionSelection(index) {
    const item = document.querySelector(`[data-section-index="${index}"]`);
    const checkbox = item.querySelector('input[type="checkbox"]');

    checkbox.checked = !checkbox.checked;

    if (checkbox.checked) {
        item.classList.add('selected');
    } else {
        item.classList.remove('selected');
    }
}

/**
 * Select all sections
 */
function selectAllSections() {
    document.querySelectorAll('.section-selection-item').forEach(item => {
        const checkbox = item.querySelector('input[type="checkbox"]');
        checkbox.checked = true;
        item.classList.add('selected');
    });
}

/**
 * Deselect all sections
 */
function deselectAllSections() {
    document.querySelectorAll('.section-selection-item').forEach(item => {
        const checkbox = item.querySelector('input[type="checkbox"]');
        checkbox.checked = false;
        item.classList.remove('selected');
    });
}

/**
 * Insert selected sections into document at cursor position
 */
async function insertSelectedSectionsToDocument() {
    // Get selected section indices
    const selectedIndices = [];
    document.querySelectorAll('.section-selection-item input[type="checkbox"]:checked').forEach(checkbox => {
        const item = checkbox.closest('.section-selection-item');
        selectedIndices.push(item.dataset.sectionIndex);
    });

    if (selectedIndices.length === 0) {
        showAlert('Please select at least one section to insert', 'warning');
        return;
    }

    // Build HTML for selected sections only
    const htmlContent = await buildSelectedSectionsHTML(selectedIndices);

    // Close modal first
    const modalInstance = bootstrap.Modal.getInstance(document.getElementById('generateDocumentModal'));
    modalInstance.hide();

    // Check if Document View BlockNote editor exists
    const editor = window.blockNoteEditors && window.blockNoteEditors['sectorEditor'];

    if (!editor) {
        // Switch to Documentation tab first
        const notesTab = document.getElementById('notes-tab');
        if (notesTab) {
            notesTab.click();

            // Wait for editor to initialize (it should load automatically on tab activation)
            waitForEditorAndInsert(htmlContent);
        } else {
            showAlert('Could not find Documentation tab', 'error');
        }
    } else {
        // Editor already exists, insert immediately
        insertContentToEditor(htmlContent);
    }
}

/**
 * Poll for editor initialization and insert content when ready
 */
function waitForEditorAndInsert(htmlContent, attempts = 0) {
    const editor = window.blockNoteEditors && window.blockNoteEditors['sectorEditor'];

    if (editor) {
        // Editor is ready, insert content
        console.log('Editor found, inserting content');
        insertContentToEditor(htmlContent);
    } else if (attempts < 50) {
        // Not ready yet, try again in 300ms (max 15 seconds)
        console.log(`Waiting for editor... attempt ${attempts + 1}/50`);
        setTimeout(() => {
            waitForEditorAndInsert(htmlContent, attempts + 1);
        }, 300);
    } else {
        // Timeout after 15 seconds
        console.error('Editor initialization timeout');
        showAlert('Document editor took too long to initialize. Please refresh the page and try again.', 'error');
    }
}

/**
 * Helper function to insert content into the BlockNote editor
 */
async function insertContentToEditor(htmlContent) {
    const editor = window.blockNoteEditors && window.blockNoteEditors['sectorEditor'];

    if (!editor) {
        showAlert('Document editor not initialized. Please try again.', 'warning');
        return;
    }

    try {
        // Use the insertHTML method which is available on the React BlockNote wrapper
        if (!editor.insertHTML) {
            console.error('insertHTML method not found on editor');
            showAlert('Editor is not fully initialized. Please try again.', 'error');
            return;
        }

        // Insert the HTML content at the current cursor position
        await editor.insertHTML(htmlContent);

        showAlert('Content inserted successfully', 'success');
    } catch (error) {
        console.error('Error inserting content:', error);
        showAlert('Error inserting content: ' + error.message, 'error');
    }
}

/**
 * Build HTML for selected sections
 */
async function buildSelectedSectionsHTML(selectedIndices) {
    const htmlParts = [];

    for (const indexStr of selectedIndices) {
        if (indexStr === 'collector') {
            // Add collector notes
            htmlParts.push('<h2>📥 Additional Notes (from Collector)</h2>');
            for (const note of canvasData.collectorNotes) {
                htmlParts.push(`<h3>${note.title}</h3>`);
                htmlParts.push(note.content);
                if (note.source_reference) {
                    const sourceText = note.source_title || note.source_reference;
                    htmlParts.push(`<p><small><em>Source: <a href="${note.source_reference}" target="_blank">${sourceText}</a></em></small></p>`);
                }
                htmlParts.push('<br>');
            }
        } else {
            const section = canvasData.sections[parseInt(indexStr)];
            if (section) {
                // Section header
                const icon = section.icon || '📌';
                htmlParts.push(`<h2>${icon} ${section.title}</h2>`);

                if (section.description) {
                    htmlParts.push(`<p><em>${section.description}</em></p>`);
                }

                // Add notes
                if (section.notes && section.notes.length > 0) {
                    for (const note of section.notes) {
                        htmlParts.push(`<h3>${note.title}</h3>`);
                        htmlParts.push(note.content);

                        if (note.source_reference) {
                            const sourceText = note.source_title || note.source_reference;
                            htmlParts.push(`<p><small><em>Source: <a href="${note.source_reference}" target="_blank">${sourceText}</a></em></small></p>`);
                        }

                        if (note.tags) {
                            const tagsHtml = note.tags.split(',').map(tag =>
                                `<span style="background: #e5e7eb; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; margin-right: 4px;">${tag.trim()}</span>`
                            ).join(' ');
                            htmlParts.push(`<p>${tagsHtml}</p>`);
                        }

                        htmlParts.push('<br>');
                    }
                } else {
                    htmlParts.push('<p><em>No notes in this section yet.</em></p>');
                }

                htmlParts.push('<hr>');
            }
        }
    }

    return htmlParts.join('\n');
}

/**
 * Show alert message (reuse from company-tagging.js if available)
 */
if (typeof showAlert !== 'function') {
    function showAlert(message, type = 'info') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show`;
        alertDiv.style.position = 'fixed';
        alertDiv.style.top = '20px';
        alertDiv.style.right = '20px';
        alertDiv.style.zIndex = '9999';
        alertDiv.style.minWidth = '300px';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        document.body.appendChild(alertDiv);

        setTimeout(() => {
            alertDiv.remove();
        }, 4000);
    }
}
