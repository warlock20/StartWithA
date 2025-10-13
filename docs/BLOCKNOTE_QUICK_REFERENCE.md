# BlockNote Quick Reference

## 🚀 Quick Start (3 Steps)

### 1️⃣ Include Script
```jinja2
{% block head %}
{% include 'components/blocknote_editor_include.html' %}
{% endblock %}
```

### 2️⃣ Add Container
```html
<div id="myEditor"></div>
```

### 3️⃣ Initialize
```javascript
<script>
window.initBlockNoteEditor('myEditor', {
    getResearchNotesUrl: '{{ url_for("bp.get_notes", id=id) }}',
    saveResearchNotesUrl: '{{ url_for("bp.save_notes", id=id) }}',
    placeholder: 'Start writing...'
});
</script>
```

## 📝 Common Use Cases

### Company Research Notes
```javascript
window.initBlockNoteEditor('companyNotes', {
    getResearchNotesUrl: '/api/companies/{{ company.id }}/notes',
    saveResearchNotesUrl: '/api/companies/{{ company.id }}/notes',
    placeholder: 'Research notes for {{ company.name }}...'
});
```

### Modal Editor
```javascript
// Initialize when modal is shown
$('#noteModal').on('shown.bs.modal', function() {
    window.initBlockNoteEditor('modalEditor', {
        placeholder: 'Write your note...',
        onSave: () => console.log('Saved!')
    });
});
```

### With Snippets
```javascript
window.initBlockNoteEditor('editor', {
    // ... other config ...
    onSelectionChange: (text, selection) => {
        // Show "Save Snippet" button when text is selected
        $('#saveSnippetBtn').toggle(text.length > 0);
        window.selectedSnippetText = text;
    }
});
```

## 🔧 Configuration Options

| Option | Type | Description |
|--------|------|-------------|
| `getResearchNotesUrl` | string | URL to load content (GET) |
| `saveResearchNotesUrl` | string | URL to save content (POST) |
| `initialContent` | string | Initial content (JSON/HTML) |
| `placeholder` | string | Placeholder text |
| `onSave` | function | Callback after save |
| `onSelectionChange` | function | Callback on text selection |

## 🎯 Template Insertion

```javascript
// Insert HTML template
window.blockNoteEditorInstance.insertHTML(`
    <h2>Section Title</h2>
    <p>Content here...</p>
    <ul>
        <li>Item 1</li>
        <li>Item 2</li>
    </ul>
`);
```

## 🔌 Backend API

### GET /api/notes/:id
**Response:**
```json
{
    "success": true,
    "content": "[{\"type\":\"paragraph\",\"content\":[...]}]"
}
```

### POST /api/notes/:id
**Request:**
```json
{
    "content": "[{\"type\":\"paragraph\",\"content\":[...]}]"
}
```

**Response:**
```json
{
    "success": true,
    "message": "Saved"
}
```

## 📦 Flask Backend Example

```python
@bp.route('/api/notes/<int:id>', methods=['GET', 'POST'])
def notes(id):
    note = Note.query.get_or_404(id)

    if request.method == 'GET':
        return jsonify({
            'success': True,
            'content': note.content or ''
        })

    if request.method == 'POST':
        data = request.get_json()
        note.content = data.get('content', '')
        note.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Saved successfully'
        })
```

## 🎨 Custom Styling

```css
/* Wrapper */
.blocknote-editor-wrapper {
    min-height: 500px;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
}

/* Save status */
.editor-status.saved {
    background: #d1fae5;
    color: #065f46;
}
```

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| Editor not appearing | Check console, ensure bundle loaded |
| Content not saving | Verify API endpoint, check response format |
| Template insertion fails | Ensure `window.blockNoteEditorInstance` exists |
| Version errors | Run `npm list @blocknote/*` - all should be 0.15.11 |

## 📚 More Examples

See `/app/templates/examples/blocknote_example.html` for a complete working example.

See `/docs/BLOCKNOTE_INTEGRATION.md` for detailed documentation.

## 🔍 Where It's Used

- ✅ **Sector Research** - `/app/sectors/templates/sector_analysis.html`
- 🔄 **Company Research** - Ready to integrate
- 🔄 **Project Notes** - Ready to integrate
- 🔄 **Research Workflow** - Can replace Quill.js

## ⚡ Quick Commands

### Build Bundle
```bash
npm run build
```

### Check Versions
```bash
npm list @blocknote/core @blocknote/react @blocknote/mantine
```

### Install (if needed)
```bash
npm install @blocknote/core@0.15.11 @blocknote/react@0.15.11 @blocknote/mantine@0.15.11
```
