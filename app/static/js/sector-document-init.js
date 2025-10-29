/**
 * Sector Research Document - BlockNote Initialization
 * Initializes React BlockNote editor after bundle is loaded
 */

// Global snippet text variable (for compatibility with sector-snippets.js)
let selectedSnippetText = '';
window.selectedSnippetText = '';

// Map to store multiple editors by container ID
window.blockNoteEditors = {};

// Initialize BlockNote editor once DOM and bundle are ready
document.addEventListener('DOMContentLoaded', function() {
    // Wait for initBlockNoteEditor to be available
    const checkAndInit = setInterval(() => {
        if (window.initBlockNoteEditor) {
            clearInterval(checkAndInit);

            // Initialize editors sequentially to avoid race conditions
            initializeDocumentEditor().then(() => {
                return initializeOtherEditors();
            }).catch(err => {
                console.error('Error during editor initialization:', err);
            });
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
    return new Promise((resolve, reject) => {
        const editorContainer = document.getElementById('sectorEditor');
        if (!editorContainer) {
            resolve(); // No editor container, skip
            return;
        }

        // Clear any previous editor instance to avoid confusion
        window.blockNoteEditorInstance = null;

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
            }
        });

        // Store the editor in our map using the container ID
        // Poll until blockNoteEditorInstance is set, then store it
        let attempts = 0;
        const maxAttempts = 40; // 2 seconds / 50ms
        const storeEditor = setInterval(() => {
            attempts++;
            if (window.blockNoteEditorInstance) {
                window.blockNoteEditors['sectorEditor'] = window.blockNoteEditorInstance;
                clearInterval(storeEditor);
                resolve(); // Resolve promise when editor is stored
            } else if (attempts >= maxAttempts) {
                clearInterval(storeEditor);
                console.warn('Document editor initialization timed out');
                resolve(); // Resolve anyway to continue with other editors
            }
        }, 50);
    });
}

function initializeOtherEditors() {
    return new Promise((resolve, reject) => {
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
            // Clear the shared editor instance to prevent race condition
            window.blockNoteEditorInstance = null;

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
                    // Optional: Handle save success
                }
            });

            // Store the takeaways editor in our map
            let attempts = 0;
            const maxAttempts = 40; // 2 seconds / 50ms
            const storeTakeawaysEditor = setInterval(() => {
                attempts++;
                if (window.blockNoteEditorInstance) {
                    window.blockNoteEditors['takeawaysEditor'] = window.blockNoteEditorInstance;
                    clearInterval(storeTakeawaysEditor);
                    resolve(); // Resolve when editor is stored
                } else if (attempts >= maxAttempts) {
                    clearInterval(storeTakeawaysEditor);
                    console.warn('Takeaways editor initialization timed out');
                    resolve(); // Resolve anyway
                }
            }, 50);
        } else {
            resolve(); // No takeaways editor, resolve immediately
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
    });
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
    try {
        // Get the MAIN DOCUMENT editor specifically from the map by container ID
        const editorToUse = window.blockNoteEditors['sectorEditor'];

        // Check if editor is ready
        if (!editorToUse) {
            console.error('Main document editor (sectorEditor) not found in editors map');
            alert('Main editor is still loading. Please wait a moment and try again.');
            return;
        }

        if (!editorToUse.insertHTML) {
            console.error('insertHTML method not found on sectorEditor');
            alert('Editor is not fully initialized. Please refresh the page and try again.');
            return;
        }

        // Fetch template content from backend
        const response = await fetch(`/sectors/template/${templateKey}`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (!data.success) {
            alert('Error loading template: ' + (data.error || 'Unknown error'));
            return;
        }

        if (!data.content) {
            alert('Template content is empty');
            return;
        }

        // Get current document state before insertion
        const beforeBlocks = editorToUse.editor.document.length;

        // Insert the HTML content
        try {
            await editorToUse.insertHTML(data.content);
        } catch (insertError) {
            console.error('insertHTML threw an error:', insertError);
            throw insertError;
        }

        // Check if blocks were actually added
        await new Promise(resolve => setTimeout(resolve, 200));
        const afterBlocks = editorToUse.editor.document.length;

        if (afterBlocks === beforeBlocks) {
            console.warn('⚠️ No blocks were added! InsertHTML may have failed silently.');
            alert('Template insertion failed. The content could not be added to the editor.');
            return;
        }

        // Scroll to show the inserted content in the MAIN document editor
        setTimeout(() => {
            const editor = editorToUse.editor;
            if (editor) {
                // Find the main document editor container specifically
                const editorElement = document.querySelector('#sectorEditor .bn-container');
                if (editorElement) {
                    editorElement.scrollTop = editorElement.scrollHeight;
                }
            }
        }, 100);

        // Close the modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('templatesModal'));
        if (modal) {
            modal.hide();
        }

    } catch (err) {
        console.error('Error inserting template:', err);
        alert('Error loading template: ' + err.message);
    }
}

// Make insertTemplate globally available
window.insertTemplate = insertTemplate;
