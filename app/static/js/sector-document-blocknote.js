/**
 * Sector Research Document - BlockNote Editor
 * Replaces Quill.js with BlockNote for a Notion-like editing experience
 */

// Global BlockNote editor instance
let blockNoteEditor = null;
let saveTimer;

// Import BlockNote from CDN (loaded as module)
let BlockNote;

// Make editor globally accessible
window.documentBlockNote = null;

// ==================== BLOCKNOTE EDITOR INITIALIZATION ====================

document.addEventListener('DOMContentLoaded', async function() {
    // Initialize other editors (Quill-based) immediately
    initializeOtherEditors();

    // Check if Documentation tab is active
    const notesTab = document.getElementById('notes');
    if (notesTab && notesTab.classList.contains('active')) {
        // Tab is active, initialize immediately
        await initializeBlockNote();
        setTimeout(loadContent, 100);
    } else {
        // Tab is not active, wait for it to be shown
        const notesTabButton = document.getElementById('notes-tab');
        if (notesTabButton) {
            notesTabButton.addEventListener('shown.bs.tab', async function(event) {
                if (!window.documentBlockNote) {
                    await initializeBlockNote();
                    setTimeout(loadContent, 100);
                }
            }, { once: true });
        }
    }
});

// Make function globally accessible
window.initializeBlockNote = async function initializeBlockNote() {
    // Check if already initialized
    if (window.documentBlockNote) {
        console.log('BlockNote already initialized');
        return window.documentBlockNote;
    }

    try {
        console.log('Starting BlockNote initialization...');
        // Import BlockNote modules from CDN
        const BlockNoteCore = await import('https://cdn.jsdelivr.net/npm/@blocknote/core@latest/dist/browser/index.js');
        const BlockNoteMantine = await import('https://cdn.jsdelivr.net/npm/@blocknote/mantine@latest/dist/browser/index.js');

        // Create BlockNote editor
        blockNoteEditor = BlockNoteCore.BlockNoteEditor.create({
            domElement: document.getElementById('sectorEditor'),
            uploadFile: async (file) => {
                // Handle file uploads (images, etc.)
                // For now, convert to base64
                return new Promise((resolve, reject) => {
                    if (file.size > 5 * 1024 * 1024) {
                        reject('File size must be less than 5MB');
                        return;
                    }

                    const reader = new FileReader();
                    reader.onload = (e) => resolve(e.target.result);
                    reader.onerror = () => reject('Failed to read file');
                    reader.readAsDataURL(file);
                });
            }
        });

        // Make globally accessible
        window.documentBlockNote = blockNoteEditor;

        // Auto-save on changes
        blockNoteEditor.onChange(() => {
            updateStatus('saving');
            clearTimeout(saveTimer);
            saveTimer = setTimeout(saveResearchNotes, 2000);
        });

        // Track text selection for snippet saving
        blockNoteEditor.onSelectionChange(() => {
            handleTextSelection();
        });

        console.log('BlockNote editor initialized successfully');
        return blockNoteEditor;

    } catch (error) {
        console.error('Failed to initialize BlockNote:', error);
        alert('Failed to initialize editor. Please refresh the page.');
        throw error;
    }
};

// Initialize other Quill editors (AI Insights, Takeaways, Note Modal)
function initializeOtherEditors() {
    // AI Insights Editor (Quill)
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

    // Key Takeaways Editor (Quill)
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

// ==================== CONTENT LOADING ====================

async function loadContent() {
    if (!blockNoteEditor) {
        console.error('BlockNote editor not initialized');
        return;
    }

    try {
        const response = await fetch(window.sectorUrls.getResearchNotes);
        const data = await response.json();

        console.log('Loaded content:', data);

        if (data.success) {
            if (data.content) {
                // Check if content is BlockNote format (JSON) or HTML (legacy Quill)
                try {
                    const blocks = JSON.parse(data.content);
                    // It's BlockNote JSON format
                    await blockNoteEditor.replaceBlocks(blockNoteEditor.document, blocks);
                } catch (e) {
                    // It's HTML from Quill - convert to BlockNote
                    const blocks = htmlToBlockNote(data.content);
                    await blockNoteEditor.replaceBlocks(blockNoteEditor.document, blocks);
                }
            }

            // Load takeaways (still using Quill)
            if (data.takeaways && window.takeawaysQuill) {
                window.takeawaysQuill.root.innerHTML = data.takeaways;
            }
        }
    } catch (err) {
        console.error('Error loading content:', err);
        updateStatus('error');
    }
}

// Convert HTML (from Quill) to BlockNote blocks
function htmlToBlockNote(html) {
    // Simple HTML to BlockNote conversion
    // This is a basic implementation - you may need to enhance it

    if (!html || html.trim() === '') {
        return [];
    }

    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    const blocks = [];

    // Process each top-level element
    doc.body.childNodes.forEach(node => {
        if (node.nodeType === Node.ELEMENT_NODE) {
            const block = elementToBlock(node);
            if (block) blocks.push(block);
        } else if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) {
            blocks.push({
                type: 'paragraph',
                content: [{ type: 'text', text: node.textContent, styles: {} }]
            });
        }
    });

    return blocks.length > 0 ? blocks : [{ type: 'paragraph', content: [] }];
}

function elementToBlock(element) {
    const tagName = element.tagName.toLowerCase();

    // Headings
    if (tagName.match(/^h[1-6]$/)) {
        const level = parseInt(tagName.charAt(1));
        return {
            type: 'heading',
            props: { level: Math.min(level, 3) }, // BlockNote supports h1-h3
            content: getInlineContent(element)
        };
    }

    // Lists
    if (tagName === 'ul' || tagName === 'ol') {
        const listType = tagName === 'ul' ? 'bulletListItem' : 'numberedListItem';
        const items = [];
        element.querySelectorAll('li').forEach(li => {
            items.push({
                type: listType,
                content: getInlineContent(li)
            });
        });
        return items.length > 0 ? items[0] : null; // Return first item (BlockNote handles lists differently)
    }

    // Paragraph
    return {
        type: 'paragraph',
        content: getInlineContent(element)
    };
}

function getInlineContent(element) {
    const content = [];
    const text = element.textContent.trim();

    if (text) {
        const styles = {};

        // Check for formatting
        if (element.querySelector('strong, b')) styles.bold = true;
        if (element.querySelector('em, i')) styles.italic = true;
        if (element.querySelector('u')) styles.underline = true;
        if (element.querySelector('s, strike')) styles.strike = true;

        content.push({
            type: 'text',
            text: text,
            styles: styles
        });
    }

    return content;
}

// ==================== SAVING ====================

async function saveResearchNotes() {
    if (!blockNoteEditor) {
        console.error('BlockNote editor not initialized');
        return;
    }

    try {
        // Get content as JSON (BlockNote format)
        const blocks = blockNoteEditor.document;
        const content = JSON.stringify(blocks);

        const response = await fetch(window.sectorUrls.saveResearchNotes, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: content })
        });

        const data = await response.json();

        if (data.success) {
            updateStatus('saved');
        } else {
            updateStatus('error');
        }
    } catch (error) {
        console.error('Error saving:', error);
        updateStatus('error');
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

function updateStatus(status) {
    const statusDiv = document.getElementById('editorStatus');
    if (!statusDiv) return;

    statusDiv.className = 'editor-status ' + status;

    if (status === 'saving') {
        statusDiv.innerHTML = '<i class="bi bi-hourglass-split"></i> <span>Saving...</span>';
    } else if (status === 'saved') {
        statusDiv.innerHTML = '<i class="bi bi-check-circle-fill"></i> <span>Saved</span>';
    } else if (status === 'error') {
        statusDiv.innerHTML = '<i class="bi bi-exclamation-circle-fill"></i> <span>Error</span>';
    }
}

// ==================== TEXT SELECTION FOR SNIPPETS ====================

let selectedSnippetText = '';
let selectedRange = null;

function handleTextSelection() {
    if (!blockNoteEditor) return;

    const btn = document.getElementById('saveSnippetBtn');
    if (!btn) return;

    try {
        // Get selected text from BlockNote
        const selection = window.getSelection();
        const selectedText = selection.toString().trim();

        if (selectedText && selectedText.length > 0) {
            // Text is selected
            selectedSnippetText = selectedText;
            selectedRange = selection.getRangeAt(0);

            // Show the button near the selection
            btn.style.display = 'block';
            // Position it at a fixed location for now (can be improved)
            btn.style.position = 'fixed';
            btn.style.bottom = '20px';
            btn.style.right = '20px';
        } else {
            // No selection - hide button but DON'T clear the saved text yet
            btn.style.display = 'none';
        }
    } catch (error) {
        console.error('Error handling selection:', error);
        btn.style.display = 'none';
    }
}

// Function to clear saved snippet (called after saving)
function clearSavedSnippet() {
    selectedSnippetText = '';
    selectedRange = null;
}

// ==================== TEMPLATE INSERTION ====================

async function insertTemplate(templateKey) {
    if (!blockNoteEditor) {
        alert('Editor not ready yet');
        return;
    }

    try {
        const response = await fetch(`/sectors/template/${templateKey}`);
        const data = await response.json();

        if (data.success && data.content) {
            // Convert HTML template to BlockNote blocks
            const blocks = htmlToBlockNote(data.content);

            // Insert blocks at current cursor position
            const currentBlock = blockNoteEditor.getTextCursorPosition().block;
            await blockNoteEditor.insertBlocks(blocks, currentBlock);

            // Trigger save
            updateStatus('saving');
            clearTimeout(saveTimer);
            saveTimer = setTimeout(saveResearchNotes, 1000);

            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('templatesModal'));
            if (modal) modal.hide();
        } else {
            alert('Error loading template: ' + (data.error || 'Unknown error'));
        }
    } catch (err) {
        console.error('Error fetching template:', err);
        alert('Error loading template');
    }
}

// ==================== AI CONTENT INSERTION ====================

async function insertAIContent() {
    if (!window.aiQuill || !blockNoteEditor) {
        alert('Editors not ready');
        return;
    }

    const aiContent = window.aiQuill.root.innerHTML;
    const sourceUrl = document.getElementById('aiSourceUrl').value;
    const aiType = document.getElementById('aiSourceType').value;
    const prompt = document.getElementById('aiPrompt').value;
    const addToSources = document.getElementById('addToSources').checked;

    // Check if there's content
    if (window.aiQuill.getText().trim().length === 0) {
        alert('Please paste some content first');
        return;
    }

    // Convert HTML to BlockNote blocks
    const blocks = htmlToBlockNote(aiContent);

    // Insert blocks at current cursor position
    const currentBlock = blockNoteEditor.getTextCursorPosition().block;
    await blockNoteEditor.insertBlocks(blocks, currentBlock);

    // Save to sources if requested
    if (addToSources && sourceUrl) {
        fetch(window.sectorUrls.addSource, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: sourceUrl,
                source_type: aiType,
                notes: prompt || 'AI-generated content'
            })
        })
        .then(response => response.json())
        .catch(err => console.error('Error saving source:', err));
    }

    // Clear AI editor and close modal
    window.aiQuill.setText('');
    document.getElementById('aiSourceUrl').value = '';
    document.getElementById('aiPrompt').value = '';

    const modal = bootstrap.Modal.getInstance(document.getElementById('pasteFromAIModal'));
    modal.hide();

    alert('Content inserted!');
}

// ==================== GENERATE DOCUMENT FROM CANVAS ====================

async function generateDocumentFromCanvas() {
    if (!blockNoteEditor) {
        alert('Editor not ready');
        return;
    }

    // Check if there's existing content
    const blocks = blockNoteEditor.document;
    const hasContent = blocks.length > 1 || (blocks.length === 1 && blocks[0].content && blocks[0].content.length > 0);

    if (hasContent) {
        if (!confirm('This will replace your existing document content with content from the Research Canvas. Continue?')) {
            return;
        }
    }

    try {
        const response = await fetch(window.sectorUrls.generateDocument);
        const data = await response.json();

        if (data.success) {
            // Convert HTML to BlockNote blocks
            const blocks = htmlToBlockNote(data.html);

            // Replace all content
            await blockNoteEditor.replaceBlocks(blockNoteEditor.document, blocks);

            // Save immediately
            await saveResearchNotes();

            alert('Document generated from canvas! You can now edit and refine it.');
        } else {
            alert('Error generating document: ' + (data.error || 'Unknown error'));
        }
    } catch (err) {
        console.error('Error:', err);
        alert('Error generating document');
    }
}

// Make functions globally available
window.insertTemplate = insertTemplate;
window.insertAIContent = insertAIContent;
window.generateDocumentFromCanvas = generateDocumentFromCanvas;
window.clearSavedSnippet = clearSavedSnippet;
