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

#### 7. Research Progress Enhancements
**Note:** The Research Progress bar already exists (lines 86-98 in sector_analysis.html) showing progress score and stage.

**Enhancement Options:**
- [x] **Progress Breakdown Modal** (Priority: High) ✅ COMPLETED
  - Click progress bar to see detailed breakdown
  - Show individual metric scores (word count, time, companies, sources, questions)
  - Display actionable targets ("Add 3 more sources to reach 80%")
  - Show weighted contribution of each metric
  - Visual breakdown with progress bars for each component
  - **Future Enhancement:** Allow users to customize scoring parameters (weights, thresholds)

- [ ] **Progress History Chart** (Priority: Medium)
  - Track progress score over time
  - Display line/area chart showing research momentum
  - Identify inactive periods
  - Requires new database field/table to store snapshots

- [ ] **Research Quality Indicators** (Priority: Medium - AI)
  - AI-powered quality assessment beyond quantity
  - Depth score (multiple sources per company, cross-references)
  - Recency warning (last updated > 14 days)
  - Coverage score (sections with content vs empty)
  - Source diversity (mix of articles, reports, videos)
  - Requires smart algorithm/AI to evaluate quality

- [ ] **Smart Suggestions Panel** (Priority: Low - AI)
  - AI-powered next steps based on current state
  - Personalized guidance ("Deep dive into 3 more companies")
  - Context-aware recommendations
  - Reduce "what should I do next?" friction

- [ ] **Research Completeness Checklist** (Priority: Low)
  - Structured checklist of research components
  - Clear actionable items (Porter's 5 Forces, Competitive Analysis, etc.)
  - Visual completion tracking

#### 8. Quick Templates ✅ COMPLETED
- [x] Create section template system
- [x] Pre-built templates:
  - [x] Porter's 5 Forces
  - [x] SWOT Analysis
  - [x] Competitive Landscape
  - [x] Financial Analysis
  - [x] Risk Assessment
- [x] One-click template application (Documentation)
- [ ] Allow users to save custom templates (Future enhancement)

#### 9. Search Within Research
- [ ] Add search bar to research page
- [ ] Search across all tabs (notes, snippets, sources, etc.)
- [ ] Highlight matching text in results
- [ ] Filter by note type, section, category
- [ ] Show search results count

#### 10. Smart AI Integration

**Architecture Plan:**
```
app/ai/
├── prompts/          # Prompt templates (easy to tune)
├── providers/        # AI provider abstraction (Gemini, OpenAI)
└── services/         # Business logic (summarizer, categorizer, etc.)
```

**Implementation Phases:**

**Phase 1: Foundation** 🏗️ ✅ COMPLETED
- [x] Create AI module structure (`app/ai/`)
- [x] Abstract provider interface (`providers/base.py`)
- [x] Implement Gemini provider (`providers/gemini.py`)
- [x] Create prompt management system (`prompts/`)

**Phase 2: Quick Wins** 🟢 (LOW HANGING FRUIT)
- [x] **Feature 1: Generate Section Summaries** → Key Takeaways tab ✅ COMPLETED
  - [x] Add "✨ Generate AI Summary" button to Key Takeaways tab
  - [x] Collect all research data (documentation, canvas notes, snippets, sources)
  - [x] Generate 5-7 bullet point summary with AI
  - [x] Insert into editor for user review/editing
  - [x] Tunable: prompt template, bullet count, focus areas, tone
  - [x] Backend route: `/sectors/<sector_name>/generate-ai-summary`
  - [x] Service layer: `SummarizationService` with clean architecture
  - [x] Prompt templates in `app/ai/prompts/sector_summaries.py`
  - [x] JavaScript integration with loading states and error handling

- [ ] **Feature 5: AI-Powered Tagging Suggestions** → Note modal enhancement
  - Smart tag autocomplete in note modal
  - Layer 1: Show existing tags from database
  - Layer 2: AI analyzes note content and suggests relevant tags
  - Tunable: suggestion count, confidence threshold

**Phase 3: Medium Features** 🟡
- [ ] **Feature 2: Auto-Categorize Notes Using AI**
  - Option A: Auto-suggest category/tags during note creation
  - Suggest note type, tags, and best section
  - User approves/rejects suggestions
  - Tunable: category taxonomy, confidence threshold, context window

- [ ] **Feature 3: Suggest Related Notes/Snippets**
  - Show "Related Content" in View Note modal
  - Start with keyword matching + tag overlap
  - Future: Upgrade to semantic similarity with embeddings
  - Show top 3-5 related items

**Phase 4: Advanced Features** 🟠 (FUTURE)
- [ ] **Feature 4: Generate Key Insights from Research** (Meta-analysis)
  - AI analyzes entire research body
  - Identify patterns, contradictions, gaps
  - Investment implications
  - Research gap detection
  - Regenerate on demand

- [ ] Semantic search with embeddings (Gemini embedding API)
- [ ] Background periodic insights generation
- [ ] AI research quality scoring

**Cost Control Considerations:**
- [ ] Cache AI responses to avoid redundant calls
- [ ] Rate limiting (max X calls per hour/day)
- [ ] Token/cost tracking and display
- [ ] User settings for AI feature opt-in/opt-out

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
Web Clipper Browser Extension: This is a power-user feature, but it's a game-changer. A browser extension would allow your users to be on any website, highlight a piece of text, and with one click, send it directly to their sector research notes on your platform. The extension could automatically capture the source URL, and the user could even add a quick note or tag right from the extension.

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
