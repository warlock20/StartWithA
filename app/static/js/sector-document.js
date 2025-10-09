/**
 * Sector Research Document - Editor Management
 * Handles Quill editors, document generation, and auto-save
 */

// Global Quill instances
let quill, aiQuill, takeawaysQuill;
let saveTimer;

// ==================== QUILL EDITOR INITIALIZATION ====================

document.addEventListener('DOMContentLoaded', function() {
    initializeEditors();
    // Load content after editors are fully initialized
    setTimeout(loadContent, 100);
});

function initializeEditors() {
    // Main Research Notes Editor
    quill = new Quill('#sectorEditor', {
        theme: 'snow',
        placeholder: 'Start your sector research here... Use templates above for structured analysis.',
        modules: {
            toolbar: [
                [{ 'header': [1, 2, 3, 4, false] }],
                ['bold', 'italic', 'underline', 'strike'],
                [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                [{ 'indent': '-1'}, { 'indent': '+1' }],
                [{ 'color': [] }, { 'background': [] }],
                ['link', 'image'],
                ['clean']
            ],
            clipboard: {
                matchVisual: false,
                matchers: [
                    // Custom matcher to clean up pasted content from AI tools
                    ['*', function(node, delta) {
                        delta.ops = delta.ops.map(op => {
                            if (op.attributes) {
                                // Keep only essential formatting attributes
                                const cleaned = {};
                                if (op.attributes.bold) cleaned.bold = true;
                                if (op.attributes.italic) cleaned.italic = true;
                                if (op.attributes.underline) cleaned.underline = true;
                                if (op.attributes.strike) cleaned.strike = true;
                                if (op.attributes.link) cleaned.link = op.attributes.link;
                                if (op.attributes.header) cleaned.header = op.attributes.header;
                                if (op.attributes.list) cleaned.list = op.attributes.list;
                                if (op.attributes.indent) cleaned.indent = op.attributes.indent;
                                if (op.attributes.code) cleaned.code = true;
                                if (op.attributes['code-block']) cleaned['code-block'] = true;
                                op.attributes = cleaned;
                            }
                            return op;
                        });
                        return delta;
                    }]
                ]
            }
        }
    });

    // Auto-save on changes
    quill.on('text-change', function() {
        updateStatus('saving');
        clearTimeout(saveTimer);
        saveTimer = setTimeout(saveResearchNotes, 2000);
    });

    // Track text selection for snippet saving
    quill.on('selection-change', handleTextSelection);

    // AI Insights Editor
    aiQuill = new Quill('#aiContentEditor', {
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

    // Key Takeaways Editor
    takeawaysQuill = new Quill('#takeawaysEditor', {
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
    takeawaysQuill.on('text-change', function() {
        clearTimeout(saveTimer);
        saveTimer = setTimeout(saveTakeaways, 2000);
    });

    // Initialize Note Content Quill Editor (for modals)
    window.noteQuill = new Quill('#noteContentEditor', {
        theme: 'snow',
        placeholder: 'Write your note here...',
        modules: {
            toolbar: [
                [{ 'header': [3, 4, false] }],
                ['bold', 'italic', 'underline'],
                [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                ['link'],
                ['clean']
            ],
            clipboard: {
                matchVisual: false,
                matchers: [
                    ['*', function(node, delta) {
                        delta.ops = delta.ops.map(op => {
                            if (op.attributes) {
                                const cleaned = {};
                                if (op.attributes.bold) cleaned.bold = true;
                                if (op.attributes.italic) cleaned.italic = true;
                                if (op.attributes.underline) cleaned.underline = true;
                                if (op.attributes.link) cleaned.link = op.attributes.link;
                                if (op.attributes.header) cleaned.header = op.attributes.header;
                                if (op.attributes.list) cleaned.list = op.attributes.list;
                                op.attributes = cleaned;
                            }
                            return op;
                        });
                        return delta;
                    }]
                ]
            }
        }
    });
}

// ==================== CONTENT LOADING ====================

function loadContent() {
    // Load research notes
    fetch(window.sectorUrls.getResearchNotes)
        .then(response => response.json())
        .then(data => {
            console.log('Loaded content:', data);
            if (data.success) {
                if (data.content) {
                    quill.root.innerHTML = data.content;
                }
                if (data.takeaways) {
                    takeawaysQuill.root.innerHTML = data.takeaways;
                }
            }
        })
        .catch(err => {
            console.error('Error loading content:', err);
            updateStatus('error');
        });
}

// ==================== SAVING ====================

function saveResearchNotes() {
    const content = quill.root.innerHTML;

    fetch(window.sectorUrls.saveResearchNotes, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: content })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            updateStatus('saved');
        } else {
            updateStatus('error');
        }
    })
    .catch(() => updateStatus('error'));
}

function saveTakeaways() {
    const content = takeawaysQuill.root.innerHTML;

    fetch(window.sectorUrls.saveResearchNotes, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ takeaways: content })
    })
    .then(response => response.json())
    .catch(err => console.error('Error saving takeaways:', err));
}

function updateStatus(status) {
    const statusDiv = document.getElementById('editorStatus');

    statusDiv.className = 'editor-status ' + status;

    if (status === 'saving') {
        statusDiv.innerHTML = '<i class="bi bi-hourglass-split"></i> <span>Saving...</span>';
    } else if (status === 'saved') {
        statusDiv.innerHTML = '<i class="bi bi-check-circle-fill"></i> <span>Saved</span>';
    } else if (status === 'error') {
        statusDiv.innerHTML = '<i class="bi bi-exclamation-circle-fill"></i> <span>Error</span>';
    }
}

// ==================== GENERATE DOCUMENT FROM CANVAS ====================

function generateDocumentFromCanvas() {
    // Check if there's existing content
    const existingContent = quill.getText().trim();
    if (existingContent.length > 0) {
        if (!confirm('This will replace your existing document content with content from the Research Canvas. Continue?')) {
            return;
        }
    }

    // Fetch canvas data and generate document
    fetch(window.sectorUrls.generateDocument)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Insert generated HTML into the editor
                quill.root.innerHTML = data.html;

                // Save immediately
                saveResearchNotes();

                alert('Document generated from canvas! You can now edit and refine it.');
            } else {
                alert('Error generating document: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(err => {
            console.error('Error:', err);
            alert('Error generating document');
        });
}

// ==================== AI CONTENT INSERTION ====================

function insertAIContent() {
    const aiContent = aiQuill.root.innerHTML;
    const sourceUrl = document.getElementById('aiSourceUrl').value;
    const aiType = document.getElementById('aiSourceType').value;
    const prompt = document.getElementById('aiPrompt').value;
    const addToSources = document.getElementById('addToSources').checked;

    // Check if there's content
    if (aiQuill.getText().trim().length === 0) {
        alert('Please paste some content first');
        return;
    }

    // Insert into main editor at cursor position
    const range = quill.getSelection() || { index: quill.getLength() };
    quill.clipboard.dangerouslyPasteHTML(range.index, aiContent);

    // Save to sources if requested
    if (addToSources && sourceUrl) {
        saveAISource(sourceUrl, aiType, prompt);
    }

    // Clear AI editor and close modal
    aiQuill.setText('');
    document.getElementById('aiSourceUrl').value = '';
    document.getElementById('aiPrompt').value = '';

    const modal = bootstrap.Modal.getInstance(document.getElementById('pasteFromAIModal'));
    modal.hide();

    alert('Content inserted!');
}

function saveAISource(url, type, prompt) {
    fetch(window.sectorUrls.addSource, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            url: url,
            source_type: type,
            notes: prompt || 'AI-generated content'
        })
    })
    .then(response => response.json())
    .catch(err => console.error('Error saving source:', err));
}

// ==================== TEXT SELECTION FOR SNIPPETS ====================

let selectedSnippetText = '';

function handleTextSelection(range, oldRange, source) {
    const btn = document.getElementById('saveSnippetBtn');

    if (range && range.length > 0) {
        // Text is selected
        selectedSnippetText = quill.getText(range.index, range.length);

        // Position the button near the selection
        const bounds = quill.getBounds(range.index, range.length);
        btn.style.display = 'block';
        btn.style.top = (bounds.bottom + 10) + 'px';
        btn.style.left = bounds.left + 'px';
    } else {
        // No selection
        btn.style.display = 'none';
        selectedSnippetText = '';
    }
}
