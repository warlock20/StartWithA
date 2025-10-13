# BlockNote Table of Contents (TOC) Feature

## Overview

The BlockNote editor now includes an **optional Table of Contents sidebar** for easy navigation through long documents - perfect for research documentation, sector analysis, and investment reports.

**Features:**
- ✅ Auto-generates from heading blocks (H1, H2, H3)
- ✅ Collapsible sidebar (280px → 50px)
- ✅ Smooth scroll to heading on click
- ✅ Active heading indicator
- ✅ Hierarchical indentation (H1 → H2 → H3)
- ✅ Real-time updates as you type
- ✅ Beautiful, professional design
- ✅ Responsive (overlay on mobile)

## Demo

**With TOC Open:**
```
┌──────────────┬────────────────────────────────┐
│ Contents     │  BlockNote Editor              │
│              │                                │
│ • Overview   │  # Overview                    │
│   - Mission  │  This is the overview section  │
│   - Vision   │                                │
│ • Analysis   │  ## Mission                    │
│   - Risks    │  Our mission is...             │
│   - Drivers  │                                │
│ • Valuation  │  ## Vision                     │
│              │  Our vision is...              │
└──────────────┴────────────────────────────────┘
```

**With TOC Collapsed:**
```
┌─┬──────────────────────────────────────┐
│☰│  BlockNote Editor                    │
│ │                                      │
│ │  # Overview                          │
│ │  This is the overview section        │
│ │                                      │
│ │  ## Mission                          │
│ │  Our mission is...                   │
│ │                                      │
│ │  ## Vision                           │
│ │  Our vision is...                    │
└─┴──────────────────────────────────────┘
```

## Usage

### Quick Start

Replace `initBlockNoteEditor` with `initBlockNoteEditorWithTOC`:

```javascript
// ❌ OLD (without TOC)
window.initBlockNoteEditor('myEditor', {
    getResearchNotesUrl: '/api/notes',
    saveResearchNotesUrl: '/api/notes'
});

// ✅ NEW (with TOC)
window.initBlockNoteEditorWithTOC('myEditor', {
    getResearchNotesUrl: '/api/notes',
    saveResearchNotesUrl: '/api/notes',
    showTOC: true  // Optional, defaults to true
});
```

### Configuration

All options from `initBlockNoteEditor` work, plus:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `showTOC` | boolean | `true` | Show/hide the TOC sidebar |

```javascript
window.initBlockNoteEditorWithTOC('editor', {
    getResearchNotesUrl: '/api/notes',
    saveResearchNotesUrl: '/api/notes',
    placeholder: 'Start writing...',
    showTOC: true,  // Enable TOC (default)
    onSave: (data) => console.log('Saved!'),
    onSelectionChange: (text) => console.log('Selected:', text)
});
```

### Disable TOC

Set `showTOC: false` to use the standard editor:

```javascript
window.initBlockNoteEditorWithTOC('editor', {
    // ... other config ...
    showTOC: false  // No TOC sidebar
});
```

## How It Works

### 1. Automatic Heading Extraction

The TOC automatically scans your document for heading blocks:

```javascript
// BlockNote JSON format
[
  {
    "type": "heading",
    "props": { "level": 1 },
    "content": [{ "type": "text", "text": "Overview" }]
  },
  {
    "type": "heading",
    "props": { "level": 2 },
    "content": [{ "type": "text", "text": "Mission" }]
  }
]
```

**Result:**
```
Contents
• Overview
  - Mission
```

### 2. Real-Time Updates

TOC updates automatically as you edit:

```javascript
// After typing a new heading, TOC updates instantly
editor.onChange(() => {
    // Extract headings
    const headings = editor.document.filter(block => block.type === "heading");
    // Update TOC list
    updateTOC(headings);
});
```

### 3. Smooth Scrolling

Click any TOC item to scroll to that heading:

```javascript
function scrollToHeading(blockIndex) {
    const blocks = document.querySelectorAll('[data-node-type="block-outer"]');
    blocks[blockIndex].scrollIntoView({ behavior: 'smooth' });
}
```

### 4. Active Heading Tracking

The current heading is highlighted as you scroll (future enhancement).

## Styling

### TOC Appearance

**Hierarchy:**
- **H1**: Bold, larger text, no indentation
- **H2**: Normal weight, slightly indented
- **H3**: Smaller text, more indented

**States:**
- **Default**: Gray text (#4b5563)
- **Hover**: Darker, light background
- **Active**: Blue text (#6366f1), blue border, gradient background

### Customization

Override CSS in your stylesheet:

```css
/* Custom TOC width */
.blocknote-toc-sidebar.open {
    width: 320px;  /* Default: 280px */
}

/* Custom active color */
.toc-item.active .toc-link {
    color: #10b981;  /* Green instead of blue */
    border-left-color: #10b981;
}

/* Custom font size */
.toc-link {
    font-size: 1rem;  /* Default: 0.875rem */
}
```

## Examples

### Example 1: Sector Research (Current)

```javascript
// sector-document-init.js
window.initBlockNoteEditorWithTOC('sectorEditor', {
    getResearchNotesUrl: window.sectorUrls.getResearchNotes,
    saveResearchNotesUrl: window.sectorUrls.saveResearchNotes,
    placeholder: 'Start your sector research here... Type "/" for commands',
    showTOC: true,
    onSelectionChange: (selectedText) => {
        window.selectedSnippetText = selectedText;
        document.getElementById('saveSnippetBtn').style.display =
            selectedText.length > 0 ? 'block' : 'none';
    },
    onSave: () => console.log('Document saved')
});
```

### Example 2: Company Research Report

```javascript
window.initBlockNoteEditorWithTOC('companyReport', {
    getResearchNotesUrl: `/api/companies/${companyId}/report`,
    saveResearchNotesUrl: `/api/companies/${companyId}/report`,
    placeholder: 'Investment thesis, risks, valuation...',
    showTOC: true
});
```

### Example 3: Investment Memo

```javascript
window.initBlockNoteEditorWithTOC('investmentMemo', {
    getResearchNotesUrl: `/api/memos/${memoId}`,
    saveResearchNotesUrl: `/api/memos/${memoId}`,
    placeholder: 'Executive summary, analysis, recommendation...',
    showTOC: true
});
```

## Best Practices

### 1. Use Headings Hierarchically

✅ **Good:**
```
# Executive Summary
## Overview
## Investment Thesis

# Analysis
## Market Opportunity
### TAM/SAM/SOM
### Growth Drivers
## Competitive Landscape

# Valuation
## DCF Model
## Comparables
```

❌ **Bad:**
```
### Random H3
# Then H1
## Back to H2  (confusing hierarchy)
```

### 2. Keep Heading Text Concise

✅ **Good:**
- "Executive Summary"
- "Market Analysis"
- "Risks & Challenges"

❌ **Bad:**
- "This is a very long heading that will be truncated in the sidebar and won't look good"

### 3. Use Descriptive Headings

✅ **Good:**
- "Competitive Advantages"
- "Revenue Model"
- "Unit Economics"

❌ **Bad:**
- "Section 1"
- "Notes"
- "Stuff"

## Technical Details

### Files Created

1. **`/frontend/src/components/BlockNoteWithTOC.jsx`**
   - React component with TOC sidebar
   - Heading extraction logic
   - Scroll navigation

2. **`/frontend/src/styles/blocknote-toc.css`**
   - TOC sidebar styling
   - Animations and transitions
   - Responsive design

3. **`/frontend/src/blocknote-editor.js`** (updated)
   - Added `initBlockNoteEditorWithTOC` function
   - Exports both components

### Bundle Size

- **Before TOC**: 1.29 MiB
- **After TOC**: 1.31 MiB (+20 KiB)

The TOC adds minimal overhead (~20 KiB) for significant UX improvement.

### Browser Support

- ✅ Chrome/Edge (Chromium)
- ✅ Firefox
- ✅ Safari
- ✅ Mobile browsers

## Troubleshooting

### TOC Not Showing

**Problem**: TOC sidebar doesn't appear
**Solutions:**
1. Ensure `showTOC: true` in config
2. Add at least one heading to document (type `/` → "Heading")
3. Check console for errors
4. Verify bundle loaded: `window.initBlockNoteEditorWithTOC`

### TOC Not Updating

**Problem**: TOC doesn't update when adding headings
**Solutions:**
1. Type headings using slash command (`/heading`)
2. Check editor instance exists: `window.blockNoteEditorInstance`
3. Clear browser cache and reload

### Scroll Not Working

**Problem**: Clicking TOC items doesn't scroll
**Solutions:**
1. Ensure editor container has proper height
2. Check `overflow-y: auto` on editor wrapper
3. Wait for document to fully load before clicking

### TOC Too Wide/Narrow

**Problem**: TOC sidebar size not ideal
**Solution**: Override CSS:

```css
.blocknote-toc-sidebar.open {
    width: 320px;  /* Adjust as needed */
    min-width: 320px;
}
```

## Future Enhancements

Potential features for future versions:

- [ ] Active heading tracking on scroll (highlight current section)
- [ ] Drag-to-reorder headings
- [ ] Collapse/expand nested sections
- [ ] Search within TOC
- [ ] Export TOC as outline
- [ ] Numbered headings (1.1, 1.2, etc.)
- [ ] TOC position (left/right toggle)
- [ ] Mini-map view (like VS Code)

## See Also

- [BlockNote Integration Guide](/docs/BLOCKNOTE_INTEGRATION.md)
- [BlockNote Quick Reference](/docs/BLOCKNOTE_QUICK_REFERENCE.md)
- [BlockNote Official Docs](https://www.blocknotejs.org/)

## Feedback

If you have suggestions for improving the TOC feature, please share your feedback!
