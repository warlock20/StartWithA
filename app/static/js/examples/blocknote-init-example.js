/**
 * BlockNote Editor - Initialization Example
 *
 * This example shows how to initialize and work with BlockNote editor.
 * Copy and adapt this for your specific use case.
 */

// Wait for DOM to be ready
document.addEventListener('DOMContentLoaded', function() {
    initializeEditor();
});

/**
 * Initialize the BlockNote editor
 */
function initializeEditor() {
    // Check if config is available
    if (!window.editorConfig) {
        console.error('Editor config not found');
        return;
    }

    // Initialize BlockNote editor
    window.initBlockNoteEditor('myEditor', {
        // API endpoints for loading/saving content
        getResearchNotesUrl: window.editorConfig.getNotesUrl,
        saveResearchNotesUrl: window.editorConfig.saveNotesUrl,

        // Or use initial content directly
        // initialContent: window.editorConfig.initialContent,

        // Placeholder text
        placeholder: 'Start writing... Type "/" for commands',

        // Callback when content is saved
        onSave: (data) => {
            console.log('Content saved successfully:', data);
            updateLastSavedTime();
        },

        // Callback when text is selected (for snippets, highlights, etc.)
        onSelectionChange: (selectedText, selection) => {
            console.log('Text selected:', selectedText);
            // You can show a toolbar, enable "Save as Snippet" button, etc.
        }
    });

    console.log('BlockNote editor initialized successfully');
}

/**
 * Update "Last Saved" timestamp
 */
function updateLastSavedTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit'
    });

    const lastSavedElement = document.getElementById('lastSaved');
    if (lastSavedElement) {
        lastSavedElement.textContent = timeString;
    }
}

/**
 * Insert a sample template
 * This demonstrates template insertion functionality
 */
function insertSampleTemplate() {
    // Check if editor is ready
    if (!window.blockNoteEditorInstance || !window.blockNoteEditorInstance.insertHTML) {
        alert('Editor not ready. Please wait a moment and try again.');
        return;
    }

    // Sample template HTML
    const templateHTML = `
        <h2>📊 Investment Thesis</h2>
        <p><strong>Company Overview:</strong> Brief description...</p>

        <h3>Key Investment Points</h3>
        <ul>
            <li>Strong competitive advantage in...</li>
            <li>Growing market opportunity...</li>
            <li>Experienced management team...</li>
        </ul>

        <h3>Risks to Consider</h3>
        <ul>
            <li>Regulatory challenges...</li>
            <li>Market competition...</li>
            <li>Execution risks...</li>
        </ul>

        <h3>Valuation</h3>
        <p>Current valuation analysis...</p>
    `;

    // Insert template into editor
    window.blockNoteEditorInstance.insertHTML(templateHTML)
        .then(() => {
            console.log('Template inserted successfully');
        })
        .catch(error => {
            console.error('Error inserting template:', error);
            alert('Failed to insert template');
        });
}

/**
 * Export content as JSON
 * Useful for backups, exports, or further processing
 */
function exportContent() {
    if (!window.blockNoteEditorInstance || !window.blockNoteEditorInstance.editor) {
        alert('Editor not ready');
        return;
    }

    // Get current document blocks
    const blocks = window.blockNoteEditorInstance.editor.document;
    const json = JSON.stringify(blocks, null, 2);

    // Create download link
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'document-export.json';
    a.click();
    URL.revokeObjectURL(url);

    console.log('Content exported successfully');
}

/**
 * Get plain text content (for search, preview, etc.)
 */
function getPlainTextContent() {
    if (!window.blockNoteEditorInstance || !window.blockNoteEditorInstance.editor) {
        return '';
    }

    const blocks = window.blockNoteEditorInstance.editor.document;

    // Extract text from blocks (simplified)
    const textParts = blocks.map(block => {
        if (block.content && Array.isArray(block.content)) {
            return block.content
                .filter(item => item.type === 'text')
                .map(item => item.text)
                .join('');
        }
        return '';
    });

    return textParts.join('\n');
}

// Expose functions globally for template use
window.insertSampleTemplate = insertSampleTemplate;
window.exportContent = exportContent;
window.getPlainTextContent = getPlainTextContent;
