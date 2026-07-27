# Frontend - BlockNote React Editor

This directory contains the React-based BlockNote editor components for the Investment Checklist platform.

## Overview

We use a **hybrid approach**: Flask templates for most pages, React components for complex interactive editors.

## Structure

```
frontend/
├── src/
│   ├── components/        # React components
│   │   └── BlockNoteEditor.jsx
│   ├── blocks/            # Custom BlockNote blocks
│   │   ├── CitationBlock.jsx
│   │   ├── CompanyMentionBlock.jsx
│   │   └── HighlightBlock.jsx
│   ├── utils/             # Utility functions
│   └── blocknote-editor.js  # Entry point
```

## Custom Blocks

### 1. Citation Block (`/citation`)
For adding citations and references with source URLs.

**Usage**: Type `/citation` in the editor

**Features**:
- Source name (editable)
- URL link
- Access date
- Citation content

### 2. Company Mention Block (`/companyMention`)
For tagging companies in research notes.

**Usage**: Type `/company` in the editor

**Features**:
- Company name
- Ticker symbol
- Clickable link to company dashboard
- Note content

### 3. Highlight Block (`/highlight`)
For highlighting key insights with colors.

**Usage**: Type `/highlight` in the editor

**Features**:
- 5 color options (yellow, green, blue, red, purple)
- Importance levels (normal, high, critical)
- Visual indicators

## Development

### Install Dependencies
```bash
npm install
```

### Build for Production
```bash
npm run build
```

Output: `app/static/js/dist/blocknote-editor.bundle.js`

### Development Mode (Watch)
```bash
npm run dev
```

This watches for changes and rebuilds automatically.

## Usage in Flask Templates

The BlockNote editor is initialized via JavaScript:

```html
<!-- Include the bundle -->
<script defer src="{{ url_for('static', filename='js/dist/blocknote-editor.bundle.js') }}"></script>

<!-- Initialize the editor -->
<div id="sectorEditor"></div>
<script>
  window.initBlockNoteEditor('sectorEditor', {
    getResearchNotesUrl: '/api/get-notes',
    saveResearchNotesUrl: '/api/save-notes',
    placeholder: 'Start typing...',
    onSave: (data) => console.log('Saved!'),
    onSelectionChange: (text) => console.log('Selected:', text)
  });
</script>
```

## Keyboard Shortcuts

- `/` - Open slash command menu
- `Ctrl/Cmd + B` - Bold
- `Ctrl/Cmd + I` - Italic
- `Ctrl/Cmd + U` - Underline
- `Ctrl/Cmd + K` - Add link
- `Ctrl/Cmd + Z` - Undo
- `Ctrl/Cmd + Shift + Z` - Redo

## Auto-Save

The editor auto-saves content 2 seconds after you stop typing.

## Migrating from Quill

Old Quill HTML content is automatically converted to BlockNote format on first load.

## Future Enhancements

- [ ] Add more custom blocks (tables, charts, financial metrics)
- [ ] Implement collaborative editing
- [ ] Add export to PDF/Markdown
- [ ] Custom slash commands
- [ ] AI-powered suggestions
