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

    // Initialize BlockNote React editor
    window.initBlockNoteEditor('sectorEditor', {
        getResearchNotesUrl: window.sectorUrls.getResearchNotes,
        saveResearchNotesUrl: window.sectorUrls.saveResearchNotes,
        placeholder: 'Start your sector research here... Type "/" for commands',
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

    // Key Takeaways Editor (Quill - keep for now)
    if (document.getElementById('takeawaysEditor')) {
        window.takeawaysQuill = new Quill('#takeawaysEditor', {
            theme: 'snow',
            placeholder: 'Key takeaways:\n• Finding 1\n• Finding 2\n• Finding 3',
            modules: {
                toolbar: [
                    [{ 'header': [3, false] }],
                    ['bold', 'italic'],
                    [{ 'list': 'bullet' }],
                    ['clean']
                ]
            }
        });

        // Auto-save takeaways
        let saveTimer;
        window.takeawaysQuill.on('text-change', function() {
            clearTimeout(saveTimer);
            saveTimer = setTimeout(saveTakeaways, 2000);
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

function saveTakeaways() {
    if (!window.takeawaysQuill) return;

    const content = window.takeawaysQuill.root.innerHTML;

    fetch(window.sectorUrls.saveResearchNotes, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ takeaways: content })
    })
    .then(response => response.json())
    .catch(err => console.error('Error saving takeaways:', err));
}

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
        // Fetch template content from backend
        const response = await fetch(`/sectors/template/${templateKey}`);
        const data = await response.json();

        if (!data.success) {
            alert('Error loading template: ' + (data.error || 'Unknown error'));
            return;
        }

        // Call the editor's insert method (exposed by React component)
        if (window.blockNoteEditorInstance && window.blockNoteEditorInstance.insertHTML) {
            await window.blockNoteEditorInstance.insertHTML(data.content);

            // Close the modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('templatesModal'));
            if (modal) modal.hide();

            console.log(`Template "${data.name}" inserted successfully`);
        } else {
            alert('Editor not ready. Please wait a moment and try again.');
        }
    } catch (err) {
        console.error('Error inserting template:', err);
        alert('Error loading template. Please try again.');
    }
}

// Make insertTemplate globally available
window.insertTemplate = insertTemplate;
