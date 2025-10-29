/**
 * Sector Research Document - BlockNote Initialization
 * Initializes React BlockNote editor after bundle is loaded
 */

// Global snippet text variable (for compatibility with sector-snippets.js)
let selectedSnippetText = '';
window.selectedSnippetText = '';

// Initialize BlockNote editor once DOM and bundle are ready
document.addEventListener('DOMContentLoaded', function() {
    // Wait for initBlockNoteEditor to be available
    const checkAndInit = setInterval(() => {
        if (window.initBlockNoteEditor) {
            clearInterval(checkAndInit);
            initializeDocumentEditor();
            initializeOtherEditors();
        }
    }, 100);

    // Timeout after 10 seconds
    setTimeout(() => {
        clearInterval(checkAndInit);
        if (!window.initBlockNoteEditor) {
            console.error('BlockNote failed to load');
            alert('Editor failed to initialize. Please refresh the page.');
        }
    }, 10000);
});

function initializeDocumentEditor() {
    const editorContainer = document.getElementById('sectorEditor');
    if (!editorContainer) return;

    // Initialize BlockNote React editor WITH TABLE OF CONTENTS
    window.initBlockNoteEditorWithTOC('sectorEditor', {
        getResearchNotesUrl: window.sectorUrls.getResearchNotes,
        saveResearchNotesUrl: window.sectorUrls.saveResearchNotes,
        placeholder: 'Start your sector research here... Type "/" for commands',
        showTOC: true, // Enable table of contents sidebar
        onSelectionChange: (selectedText, selection) => {
            // Update global variable for snippet saving
            selectedSnippetText = selectedText;
            window.selectedSnippetText = selectedText;

            // Show/hide snippet button
            const btn = document.getElementById('saveSnippetBtn');
            if (btn) {
                if (selectedText && selectedText.length > 0) {
                    btn.style.display = 'block';
                } else {
                    btn.style.display = 'none';
                }
            }
        },
        onSave: (data) => {
            // Optional: Handle save success
            console.log('Document saved successfully');
        }
    });
}

function initializeOtherEditors() {
    // AI Insights Editor (Quill - keep for now)
    if (document.getElementById('aiContentEditor')) {
        window.aiQuill = new Quill('#aiContentEditor', {
            theme: 'snow',
            placeholder: 'Paste AI-generated content here...',
            modules: {
                toolbar: [
                    [{ 'header': [2, 3, false] }],
                    ['bold', 'italic'],
                    [{ 'list': 'bullet' }],
                    ['clean']
                ]
            }
        });
    }

    // Key Takeaways Editor (BlockNote with TOC - NEW)
    if (document.getElementById('takeawaysEditor')) {
        // Create separate URLs for takeaways
        const takeawaysUrls = {
            getTakeaways: window.sectorUrls.getResearchNotes, // Same endpoint, returns both content and takeaways
            saveTakeaways: window.sectorUrls.saveResearchNotes
        };

        // Initialize BlockNote with TOC for takeaways
        window.initBlockNoteEditorWithTOC('takeawaysEditor', {
            getResearchNotesUrl: takeawaysUrls.getTakeaways,
            saveResearchNotesUrl: takeawaysUrls.saveTakeaways,
            placeholder: 'Key takeaways:\n• Finding 1\n• Finding 2\n• Finding 3',
            showTOC: true, // Enable TOC sidebar for navigation
            contentField: 'takeaways', // Save to 'takeaways' field instead of 'content'
            onSave: (data) => {
                console.log('Takeaways saved successfully');
            }
        });
    }

    // Note Content Quill Editor (initialized when modal is shown)
    const noteModal = document.getElementById('noteModal');
    if (noteModal) {
        noteModal.addEventListener('shown.bs.modal', function() {
            if (!window.noteQuill) {
                window.noteQuill = new Quill('#noteContentEditor', {
                    theme: 'snow',
                    placeholder: 'Write your note here...',
                    modules: {
                        toolbar: [
                            [{ 'header': [3, 4, false] }],
                            ['bold', 'italic', 'underline', 'strike'],
                            [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                            [{ 'color': [] }, { 'background': [] }],
                            ['blockquote', 'code-block'],
                            ['link', 'image'],
                            ['clean']
                        ]
                    }
                });
            }
        });
    }
}

// saveTakeaways() function removed - BlockNote handles auto-save internally

// Export for use in other modules
window.selectedSnippetText = selectedSnippetText;

// Clear saved snippet function (used by sector-snippets.js)
window.clearSavedSnippet = function() {
    selectedSnippetText = '';
    window.selectedSnippetText = '';
};

// ==================== TEMPLATE INSERTION ====================

async function insertTemplate(templateKey) {
    console.log(`insertTemplate called with key: ${templateKey}`);

    try {
        // Check if editor is ready
        if (!window.blockNoteEditorInstance) {
            console.error('blockNoteEditorInstance not found on window');
            alert('Editor is still loading. Please wait a moment and try again.');
            return;
        }

        if (!window.blockNoteEditorInstance.insertHTML) {
            console.error('insertHTML method not found on blockNoteEditorInstance');
            alert('Editor is not fully initialized. Please refresh the page and try again.');
            return;
        }

        console.log('Editor found, fetching template...');

        // Fetch template content from backend
        const response = await fetch(`/sectors/template/${templateKey}`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Template data received:', data);

        if (!data.success) {
            alert('Error loading template: ' + (data.error || 'Unknown error'));
            return;
        }

        if (!data.content) {
            alert('Template content is empty');
            return;
        }

        console.log('Inserting template content...');
        console.log('HTML content length:', data.content.length);
        console.log('HTML preview:', data.content.substring(0, 200));

        // Get current document state before insertion
        const beforeBlocks = window.blockNoteEditorInstance.editor.document.length;
        console.log('Document blocks before insert:', beforeBlocks);

        // Insert the HTML content
        try {
            await window.blockNoteEditorInstance.insertHTML(data.content);
            console.log('insertHTML call completed');
        } catch (insertError) {
            console.error('insertHTML threw an error:', insertError);
            throw insertError;
        }

        // Check if blocks were actually added
        await new Promise(resolve => setTimeout(resolve, 200));
        const afterBlocks = window.blockNoteEditorInstance.editor.document.length;
        console.log('Document blocks after insert:', afterBlocks);

        if (afterBlocks === beforeBlocks) {
            console.warn('⚠️ No blocks were added! InsertHTML may have failed silently.');
            alert('Template insertion failed. The content could not be added to the editor.');
            return;
        }

        console.log('✓ Template inserted successfully -', (afterBlocks - beforeBlocks), 'new blocks added');

        // Scroll to show the inserted content
        setTimeout(() => {
            const editor = window.blockNoteEditorInstance.editor;
            if (editor) {
                // Scroll to bottom of editor to show new content
                const editorElement = document.querySelector('.bn-container');
                if (editorElement) {
                    editorElement.scrollTop = editorElement.scrollHeight;
                    console.log('Scrolled to show new content');
                }
            }
        }, 100);

        // Close the modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('templatesModal'));
        if (modal) {
            modal.hide();
            console.log('Modal closed');
        }

        // Show success message
        console.log(`✓ Template "${data.name}" inserted successfully`);

    } catch (err) {
        console.error('Error inserting template:', err);
        alert('Error loading template: ' + err.message);
    }
}

// Make insertTemplate globally available
window.insertTemplate = insertTemplate;

// Log when this script loads
console.log('sector-document-init.js loaded, insertTemplate function registered');
