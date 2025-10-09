# Sector Research Enhancement TODO

## ✅ Completed Features

### Phase 1: Atomic Notes System
- [x] Design atomic notes data model and relationships
- [x] Create `SectorSection` and `SectorNote` models
- [x] Create atomic notes canvas UI with sections
- [x] Add backend CRUD routes for sections and notes
- [x] Add modals for creating/editing sections and notes
- [x] Add JavaScript functions for CRUD operations
- [x] Implement drag and drop for reorganizing notes
- [x] Create collector/inbox pattern for unorganized notes
- [x] Add CSS module for atomic canvas styling

### Earlier Features
- [x] Enhanced Quill.js clipboard matcher for AI content
- [x] Research Sources sidebar panel
- [x] "Paste from AI" button and modal
- [x] Tabbed interface (Research Canvas, Document View, AI Insights, Sources, Snippets, Key Takeaways)
- [x] Research Snippets with category filtering
- [x] Floating "Save Snippet" button on text selection

---

## 📋 Pending Features

### Quick Wins (High Impact, Low Effort)

#### 1. Auto-tagging Company Mentions
- [ ] Create function to detect company names/tickers in pasted content
- [ ] Match against companies in database
- [ ] Automatically add company tags to notes/snippets
- [ ] Add visual indicators for tagged companies
- [ ] Link to company research pages

#### 2. Search Within Research
- [ ] Add search bar to research page
- [ ] Search across all tabs (notes, snippets, sources, etc.)
- [ ] Highlight matching text in results
- [ ] Filter by note type, section, category
- [ ] Show search results count

#### 3. Export Capabilities
- [ ] Export entire research to Markdown
- [ ] Export specific sections to Markdown
- [ ] Export to PDF with formatting
- [ ] Include sources and snippets in exports
- [ ] Option to include/exclude specific sections

#### 4. Enhanced Note Editing
- [ ] Add rich text editor to note modal (Quill.js)
- [ ] Support formatting (bold, italic, lists)
- [ ] Allow adding images to notes
- [ ] Support code snippets with syntax highlighting

#### 5. Bulk Operations
- [ ] Select multiple notes with checkboxes
- [ ] Bulk move to different section
- [ ] Bulk tag addition
- [ ] Bulk delete with confirmation

---

### Medium Effort Features

#### 6. Link Notes to Companies
- [ ] Add company picker to note modal
- [ ] Create relationship between notes and companies
- [ ] Show company notes on company detail page
- [ ] Filter canvas by linked company
- [ ] Display company context in note card

#### 7. Timeline View
- [ ] Create timeline visualization of research
- [ ] Group by date created
- [ ] Filter by note type, section
- [ ] Show research evolution over time
- [ ] Highlight key milestones

#### 8. Quick Templates
- [ ] Create section template system
- [ ] Pre-built templates:
  - [ ] Porter's 5 Forces
  - [ ] SWOT Analysis
  - [ ] Competitive Landscape
  - [ ] Financial Analysis
  - [ ] Risk Assessment
- [ ] Allow users to save custom templates
- [ ] One-click template application

#### 9. Smart AI Integration
- [ ] Generate section summaries with AI
- [ ] Auto-categorize notes using AI
- [ ] Suggest related notes/snippets
- [ ] Generate key insights from research
- [ ] AI-powered tagging suggestions

#### 10. Collaboration Features
- [ ] Share research canvas with team
- [ ] Add comments to notes
- [ ] Track who added/edited notes
- [ ] Version history for notes
- [ ] Collaborative editing

---

### Advanced Features (Phase 3)

#### 11. Browser Extension for Web Clipping
- [ ] Chrome/Firefox extension
- [ ] One-click save webpage snippets
- [ ] Auto-extract company mentions
- [ ] Auto-categorize clipped content
- [ ] Direct save to collector

#### 12. Integration with Document Imports
- [ ] Link imported PDFs to canvas notes
- [ ] Auto-extract snippets from PDFs
- [ ] Reference specific PDF pages in notes
- [ ] Show document context in notes

#### 13. Graph View
- [ ] Visualize connections between notes
- [ ] Show company relationships
- [ ] Interactive node graph
- [ ] Cluster related research

#### 14. Advanced Analytics
- [ ] Research coverage metrics
- [ ] Time spent analysis
- [ ] Note type distribution
- [ ] Source diversity analysis
- [ ] Completeness scoring

#### 15. Mobile Optimization
- [ ] Responsive canvas layout
- [ ] Touch-optimized drag and drop
- [ ] Mobile quick capture
- [ ] Offline support with sync

---

## 🐛 Known Issues / Tech Debt

- [ ] Authentication error preventing some users from testing
- [ ] Drag and drop doesn't show visual placeholder during drag
- [ ] No undo/redo functionality for note operations
- [ ] Page reload after every drag operation (could use optimistic UI)
- [ ] No keyboard shortcuts for quick actions
- [ ] Empty sections could have better empty state

---

## 🎯 Recommended Next Steps

**Priority 1 (This Week):**
1. Auto-tagging company mentions
2. Search within research
3. Enhanced note editing with rich text

**Priority 2 (Next Week):**
4. Export capabilities
5. Link notes to companies
6. Quick templates

**Priority 3 (Later):**
7. Timeline view
8. Smart AI integration
9. Collaboration features
