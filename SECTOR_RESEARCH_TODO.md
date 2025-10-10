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

#### 1. Auto-tagging Company Mentions ✅ COMPLETED
- [x] Create function to detect company names/tickers in pasted content
- [x] Match against companies in database
- [x] User confirmation workflow for suggested company tags
- [x] Add visual indicators for tagged companies
- [x] Link companies to notes and snippets
- [x] Display company tags on note/snippet cards
- [x] Support multiple companies per note

#### 2. Generate Document from Canvas ✅ COMPLETED
- [x] Create modal to select sections/notes to include
- [x] Insert at cursor position instead of replacing content
- [x] Support selecting specific sections
- [x] Auto-switch to Document View tab
- [x] Show section and note counts

#### 3. Enhanced Note Editing ✅ COMPLETED
- [x] Add rich text editor to note modal (Quill.js)
- [x] Support formatting (bold, italic, lists)
- [x] Allow adding images to notes
- [x] Support code snippets with syntax highlighting
- [x] Added color and background color options
- [x] Added blockquote support
- [x] Added strike-through formatting
- [x] Custom image upload handler with 5MB limit
- [x] Base64 image encoding for easy storage
- [x] Syntax highlighting with Highlight.js (Atom One Dark theme)

#### 4. Fixed-Height Research Workspace ✅ COMPLETED
- [x] Create professional fixed-height layout (Notion/Obsidian style)
- [x] Make research-tabs-container and sticky-sidebar same height
- [x] Add independent scrolling to each area
- [x] Implement custom scrollbars with professional styling
- [x] Add fade effects at scroll edges
- [x] Enhanced shadows and visual polish
- [x] Responsive adjustments for mobile/tablet
- [x] Remove redundant Collector from sidebar
- [x] Convert sidebar to accordion/collapsible design
- [x] Add unified container border around workspace
- [x] Fix broken company add functionality in Quick Tools

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

#### 9. Search Within Research
- [ ] Add search bar to research page
- [ ] Search across all tabs (notes, snippets, sources, etc.)
- [ ] Highlight matching text in results
- [ ] Filter by note type, section, category
- [ ] Show search results count

#### 10. Smart AI Integration
- [ ] Generate section summaries with AI
- [ ] Auto-categorize notes using AI
- [ ] Suggest related notes/snippets
- [ ] Generate key insights from research
- [ ] AI-powered tagging suggestions

#### 11. Collaboration Features
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
---

## 🎯 Recommended Next Steps

**Priority 1 (Completed):**
1. ✅ Auto-tagging company mentions
2. ✅ Generate document from canvas

**Priority 2 (This Week):**
3. ✅ Enhanced note editing with rich text
4. ✅ Fixed-height research workspace
5. Export capabilities
6. Bulk operations

**Priority 3 (Next Week):**
6. Link notes to companies (partially done - auto-tagging works)
7. Timeline view
8. Quick templates

**Priority 4 (Later):**
9. Search within research
10. Smart AI integration
11. Collaboration features
