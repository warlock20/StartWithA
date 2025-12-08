# BlockNote Editor Integration Guide

## Overview

BlockNote is a modern, Notion-like block-based rich text editor integrated into the platform. It's built with React and provides a superior editing experience compared to Quill.js.

**Benefits:**
- ✅ Block-based editing (like Notion)
- ✅ Slash commands for inserting content types
- ✅ Auto-save with debouncing
- ✅ Template insertion support
- ✅ Clean JSON storage format
- ✅ Highly customizable

## Quick Start

### 1. Include the BlockNote Script

Add to your template's `{% block head %}`:

```jinja2
{% block head %}
<!-- BlockNote Editor (React) -->
<script defer src="{{ url_for('static', filename='js/dist/blocknote-editor.bundle.js') }}"></script>
{% endblock %}
```

**OR** use the reusable include:

```jinja2
{% block head %}
{% include 'components/blocknote_editor_include.html' %}
{% endblock %}
```

### 2. Add Container Element

In your template body:

```html
<div id="myEditor"></div>
```

### 3. Initialize the Editor

Add initialization script (typically in `{% block head %}` or before `</body>`):

```html
<script>
document.addEventListener('DOMContentLoaded', function() {
    window.initBlockNoteEditor('myEditor', {
        // Required: API endpoints
        getResearchNotesUrl: '{{ url_for("your_blueprint.get_notes", id=item.id) }}',
        saveResearchNotesUrl: '{{ url_for("your_blueprint.save_notes", id=item.id) }}',

        // Optional: Configuration
        placeholder: 'Start your research here... Type "/" for commands',

        // Optional: Callbacks
        onSave: (data) => {
            console.log('Document saved successfully');
        },
        onSelectionChange: (selectedText, selection) => {
            console.log('Text selected:', selectedText);
        }
    });
});
</script>
```

## Configuration Options

### `initBlockNoteEditor(elementId, config)`

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `elementId` | string | Yes | ID of the DOM element to mount the editor |
| `config.getResearchNotesUrl` | string | No* | URL to fetch initial content (GET request) |
| `config.saveResearchNotesUrl` | string | No* | URL to save content (POST request) |
| `config.initialContent` | string | No | Initial content (JSON or HTML) - used if no fetch URL |
| `config.placeholder` | string | No | Placeholder text (default: "Start your research here...") |
| `config.onSave` | function | No | Callback after successful save |
| `config.onSelectionChange` | function | No | Callback when text selection changes |

*At least one of `getResearchNotesUrl` or `initialContent` should be provided.

## Backend API Requirements

### GET Endpoint (Load Content)

**Expected Response:**
```json
{
    "success": true,
    "content": "[{\"type\":\"paragraph\",\"content\":[{\"type\":\"text\",\"text\":\"Hello\"}]}]"
}
```

**Example Flask Route:**
```python
@bp.route('/api/notes/<int:note_id>')
def get_notes(note_id):
    note = Note.query.get_or_404(note_id)
    return jsonify({
        'success': True,
        'content': note.content or ''
    })
```

### POST Endpoint (Save Content)

**Expected Request Body:**
```json
{
    "content": "[{\"type\":\"paragraph\",\"content\":[{\"type\":\"text\",\"text\":\"Hello\"}]}]"
}
```

**Expected Response:**
```json
{
    "success": true,
    "message": "Saved successfully"
}
```

**Example Flask Route:**
```python
@bp.route('/api/notes/<int:note_id>', methods=['POST'])
def save_notes(note_id):
    note = Note.query.get_or_404(note_id)
    data = request.get_json()

    note.content = data.get('content', '')
    note.updated_at = datetime.utcnow()

    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Saved successfully'
    })
```

## Advanced Features

### Template Insertion

BlockNote exposes a global instance for template insertion:

```javascript
// Insert HTML content at cursor position
if (window.blockNoteEditorInstance && window.blockNoteEditorInstance.insertHTML) {
    await window.blockNoteEditorInstance.insertHTML('<h2>Investment Thesis</h2><p>...</p>');
}
```

**Complete Template Insertion Example:**
```javascript
async function insertTemplate(templateKey) {
    try {
        // Fetch template from backend
        const response = await fetch(`/api/templates/${templateKey}`);
        const data = await response.json();

        if (!data.success) {
            alert('Error loading template');
            return;
        }

        // Insert into editor
        if (window.blockNoteEditorInstance && window.blockNoteEditorInstance.insertHTML) {
            await window.blockNoteEditorInstance.insertHTML(data.content);
            console.log('Template inserted successfully');
        } else {
            alert('Editor not ready. Please wait and try again.');
        }
    } catch (err) {
        console.error('Error inserting template:', err);
    }
}
```

### Text Selection Snippets

Use `onSelectionChange` to enable "save as snippet" functionality:

```javascript
window.initBlockNoteEditor('myEditor', {
    // ... other config ...
    onSelectionChange: (selectedText, selection) => {
        const snippetBtn = document.getElementById('saveSnippetBtn');
        if (snippetBtn) {
            snippetBtn.style.display = selectedText.length > 0 ? 'block' : 'none';
        }

        // Store selected text globally
        window.selectedSnippetText = selectedText;
    }
});

// Save snippet button handler
function saveSnippet() {
    const text = window.selectedSnippetText;
    if (!text) return;

    // Show modal or save directly
    // ... your save logic ...
}
```

### Manual Content Retrieval

Access the editor instance for manual operations:

```javascript
// Get current document blocks
if (window.blockNoteEditorInstance) {
    const blocks = window.blockNoteEditorInstance.editor.document;
    console.log('Current content:', blocks);
}
```

## Real-World Examples

### Example 1: Sector Research (Current Implementation)

```jinja2
{% block head %}
<script defer src="{{ url_for('static', filename='js/dist/blocknote-editor.bundle.js') }}"></script>

<script>
    window.sectorUrls = {
        getResearchNotes: '{{ url_for("sectors.get_research_notes", sector_name=analysis.sector_name) }}',
        saveResearchNotes: '{{ url_for("sectors.save_research_notes", sector_name=analysis.sector_name) }}'
    };
</script>

<script src="{{ url_for('static', filename='js/sector-document-init.js') }}"></script>
{% endblock %}

{% block content %}
<div id="sectorEditor"></div>
{% endblock %}
```

**sector-document-init.js:**
```javascript
document.addEventListener('DOMContentLoaded', function() {
    window.initBlockNoteEditor('sectorEditor', {
        getResearchNotesUrl: window.sectorUrls.getResearchNotes,
        saveResearchNotesUrl: window.sectorUrls.saveResearchNotes,
        placeholder: 'Start your sector research here... Type "/" for commands',
        onSelectionChange: (selectedText, selection) => {
            window.selectedSnippetText = selectedText;
            const btn = document.getElementById('saveSnippetBtn');
            if (btn) {
                btn.style.display = selectedText.length > 0 ? 'block' : 'none';
            }
        },
        onSave: (data) => {
            console.log('Document saved successfully');
        }
    });
});
```

### Example 2: Company Research Notes

```jinja2
{% block head %}
{% include 'components/blocknote_editor_include.html' %}
{% endblock %}

{% block content %}
<div class="company-notes-container">
    <h2>Research Notes - {{ company.name }}</h2>
    <div id="companyNotesEditor"></div>
</div>

<script>
document.addEventListener('DOMContentLoaded', function() {
    window.initBlockNoteEditor('companyNotesEditor', {
        getResearchNotesUrl: '{{ url_for("companies.get_notes", company_id=company.id) }}',
        saveResearchNotesUrl: '{{ url_for("companies.save_notes", company_id=company.id) }}',
        placeholder: 'Research notes for {{ company.name }}...',
        onSave: (data) => {
            showToast('Notes saved successfully', 'success');
        }
    });
});
</script>
{% endblock %}
```

### Example 3: Note Modal (Inline Editor)

```html
<!-- Note Modal -->
<div class="modal" id="noteModal">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5>Edit Note</h5>
            </div>
            <div class="modal-body">
                <input type="text" id="noteTitle" placeholder="Title">
                <div id="noteContentEditor" style="min-height: 300px;"></div>
            </div>
            <div class="modal-footer">
                <button onclick="saveNote()">Save</button>
            </div>
        </div>
    </div>
</div>

<script>
let noteEditorInstance = null;

// Initialize when modal is shown
document.getElementById('noteModal').addEventListener('shown.bs.modal', function() {
    if (!noteEditorInstance) {
        noteEditorInstance = window.initBlockNoteEditor('noteContentEditor', {
            placeholder: 'Write your note here...',
            initialContent: '', // Will be set when editing
        });
    }
});

function saveNote() {
    if (window.blockNoteEditorInstance) {
        const content = JSON.stringify(window.blockNoteEditorInstance.editor.document);

        fetch('/api/notes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: document.getElementById('noteTitle').value,
                content: content
            })
        }).then(response => response.json())
          .then(data => {
              if (data.success) {
                  bootstrap.Modal.getInstance(document.getElementById('noteModal')).hide();
              }
          });
    }
}
</script>
```

## Migration from Quill.js

If you're migrating from Quill.js to BlockNote:

### Before (Quill.js):
```javascript
const quill = new Quill('#editor', {
    theme: 'snow',
    modules: { toolbar: [...] }
});

quill.on('text-change', function() {
    const content = quill.root.innerHTML;
    saveContent(content);
});
```

### After (BlockNote):
```javascript
window.initBlockNoteEditor('editor', {
    saveResearchNotesUrl: '/api/save',
    placeholder: 'Start writing...',
    onSave: (data) => {
        console.log('Auto-saved!');
    }
});
```

**Key Differences:**
- ✅ **Auto-save** - BlockNote handles debounced saves automatically
- ✅ **JSON Format** - BlockNote stores structured JSON (not HTML)
- ✅ **Block-based** - Content is organized in blocks (paragraphs, headings, lists)
- ✅ **No manual save** - Save is automatic after 2 seconds of inactivity

## Styling

BlockNote includes default styles. To customize:

```css
/* Custom BlockNote styles */
.blocknote-editor-wrapper {
    min-height: 500px;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
}

/* Save status indicator */
.editor-status {
    position: absolute;
    top: 10px;
    right: 10px;
    padding: 6px 12px;
    border-radius: 4px;
    font-size: 12px;
}

.editor-status.saved {
    background: #d1fae5;
    color: #065f46;
}
```

See `/frontend/src/styles/blocknote-custom.css` for the full custom stylesheet.

## Troubleshooting

### Editor Not Appearing

**Problem:** Editor div is empty, no BlockNote UI
**Solution:**
- Check browser console for errors
- Ensure `blocknote-editor.bundle.js` is loaded (check Network tab)
- Verify `initBlockNoteEditor` is called after DOM is ready

### Content Not Saving

**Problem:** Changes don't persist to database
**Solution:**
- Check `saveResearchNotesUrl` is correct
- Verify backend endpoint returns `{"success": true}`
- Check browser console for save errors
- Ensure backend accepts JSON POST requests

### Template Insertion Not Working

**Problem:** `insertTemplate` throws "Editor not ready" error
**Solution:**
- Wait for editor to initialize before calling `insertHTML`
- Check `window.blockNoteEditorInstance` exists
- Ensure editor has focus or cursor position

### Version Mismatch Errors

**Problem:** Editor crashes with "transact is not a function" or similar
**Solution:**
- Ensure all `@blocknote/*` packages are the same version
- Run: `npm list @blocknote/core @blocknote/react @blocknote/mantine`
- Rebuild bundle: `npm run build`

## Package Versions

Current versions (aligned):
```json
{
  "@blocknote/core": "^0.15.11",
  "@blocknote/react": "^0.15.11",
  "@blocknote/mantine": "^0.15.11"
}
```

## Contributing

When adding new features to BlockNote:

1. **Update React Component:** `/frontend/src/components/BlockNoteEditor.jsx`
2. **Update Init Script:** `/frontend/src/blocknote-editor.js`
3. **Rebuild Bundle:** `npm run build`
4. **Update This Documentation**

## Further Reading

- [BlockNote Documentation](https://www.blocknotejs.org/)
- [BlockNote GitHub](https://github.com/TypeCellOS/BlockNote)
- [React Integration Guide](https://www.blocknotejs.org/docs/react)
