# Research Workflow Documentation

## Overview

This document describes the investment research workflow in the Investment Checklist platform. The system supports two parallel research workflows: Company-focused and Sector-focused research, which can intersect when companies are discovered during sector research.

---

## High-Level Workflow

### Company Workflow

```
Add Company → Idea Inbox → Kill Process → [Survives] → Research
```

**Steps:**
1. **Add Company**: User adds a company to the system
2. **Idea Inbox**: Company enters the idea inbox for initial evaluation
3. **Kill Process**: Company undergoes kill process to validate investment thesis
4. **Research**: If company survives kill process, full research project is initiated

### Sector Workflow

```
Add Sector Idea → [Inbox or Research] → Sector Research → Discover Companies → [Optional: Add to Inbox]
                                                                                          ↓
                                                                                   Company Workflow
```

**Steps:**
1. **Add Sector Idea**: User identifies a sector of interest
2. **Inbox or Research**: User can either:
   - Keep idea in inbox for later
   - Proceed directly to sector research
3. **Sector Research**: User conducts research on the sector
4. **Discover Companies**: During research, user identifies relevant companies
5. **Optional Company Addition**: Companies can be added to idea inbox, which initiates the Company Workflow

### Workflow Intersection

Sector research feeds into company research through the idea inbox:
- Companies discovered during sector research can be added to the idea inbox
- Once in inbox, they follow the standard Company Workflow (Kill Process → Research)

### Key Principles

1. **Flexible Entry**: Users can start with either a company or sector
2. **Structured Progression**: Companies must pass through kill process before full research
3. **Connected Workflows**: Sector research naturally feeds company pipeline
4. **Optional Integration**: Adding sector companies to inbox is optional, allowing flexibility

---

## Technical Implementation

This section describes the current research workflow implementation, including the user journey, technical implementation, and identified areas for enhancement.

## Current Research Workflow

### 1. Research Initiation

#### Entry Points:
- **Companies Dashboard** → Research dropdown → Quick Checklist Analysis
- **Companies Dashboard** → Research dropdown → Mental Models
- **Companies Dashboard** → Research dropdown → Research Templates
- **Idea Pipeline** → Promote idea to research project

#### Route Structure:
```
/research/select-checklist-for-company/<company_id>  → Select checklist
/research/select-model/<company_id>                   → Select mental model
/research/workflow/start-project                     → Start from template
```

### 2. Research Session Structure

#### Session Flow:
1. **Session Creation** (`/research/session/<session_id>/item/<item_id>`)
2. **Question Navigation** (Previous/Next through checklist items)
3. **Answer Recording** (Text + satisfaction status)
4. **Session Completion** → Summary page

#### Technical Implementation:
- **Models**: `ResearchSession`, `ResearchAnswer`, `ChecklistItem`
- **Templates**: `research_step.html` (main research interface)
- **Routes**: `research.research_step(session_id, item_id)`

### 3. Current Research Interface Features

#### Visual Design:
- **Enhanced Question Card** with gradient styling
- **Progress Indicator** (X/Y questions completed)
- **Company Context** (Name, ticker, checklist type)
- **Question Number** with gradient badge
- **Large, Bold Question Text** (1.5rem, weight 600)

#### Interactive Features:
- **Focus Mode** toggle (press `F` or click eye icon)
  - Scales question card and increases text size
  - Changes text color to primary
  - Smooth scroll to center
- **Read Aloud** functionality (press `R` or click button)
  - Text-to-speech integration
  - Configurable rate and volume
  - Visual feedback during speech
- **Keyboard Shortcuts** for power users

#### AI Integration:
- **AI Analysis Assistant** (if question has LLM prompt)
- **Document Selection** for context
- **Model Choice** (Local/Gemini)
- **Prompt Display** and execution

### 4. Answer Recording System

#### Answer Components:
- **Answer Text** (textarea for detailed analysis)
- **Satisfaction Status** dropdown:
  - Neutral / Informational
  - ✅ Satisfied / Met
  - ❌ Not Satisfied / Not Met
  - ⚠️ Needs Attention

#### Navigation:
- **Previous** button (if not first question)
- **Save & Continue** button (auto-saves and moves to next)

### 5. Research Templates & Projects

#### Research Project System:
- **Template-Based** research workflows
- **Progress Tracking** (percentage completion)
- **Status Management** (active, paused, completed, abandoned)
- **Time Tracking** (hours spent, last worked date)
- **Decision Recording** (invest/pass/watchlist + confidence)

#### Project Management:
- **My Projects** page (`/research/workflow/my-projects`)
- **Project Dashboard** for active research
- **Project Summary** for completed research

## Current Workflow Gaps

### Research Process Integration:
1. **Missing Research Tools**:
   - No integrated web search
   - No quick access to company documents
   - No research note-taking (separate from final answer)
   - No source/link collection

2. **Question State Management**:
   - No "researching" vs "completed" status
   - No "save for later" functionality
   - No research time tracking per question

3. **Context Switching**:
   - No quick access to related documents
   - No smart suggestions based on question type
   - No integration with external research tools

### Technical Architecture

#### Key Files:
```
/app/research/
├── routes.py              # Research session management
├── templates/
│   ├── research_step.html # Main research interface
│   ├── list_research_sessions.html
│   └── session_summary.html

/app/research_workflow/
├── routes.py              # Project management
├── templates/
│   ├── my_projects.html   # Project overview
│   ├── project_dashboard.html
│   └── template_list.html
```

#### Database Models:
```python
# Core research models
ResearchSession     # Links user + company + checklist
ResearchAnswer      # Stores answers for each question
ChecklistItem       # Question definitions

# Project workflow models
ResearchProject     # Template-based research projects
ResearchTemplate    # Reusable research frameworks
WorkSession         # Time tracking for research sessions
```

## Enhancement Roadmap

### Phase 1: Research Process Integration
- Add research panel alongside questions
- Integrate document quick access
- Implement question state management
- Add research notes (separate from answers)

### Phase 2: Smart Research Tools
- Auto-generate search terms
- Context-aware document suggestions
- Source/link collection system
- Research time tracking

### Phase 3: Advanced Features
- Multi-tab research workflow
- Research session templates
- Collaborative research features
- Research quality metrics

## User Journey Examples

### Typical Research Session:
1. User selects company from dashboard
2. Chooses "Quick Checklist Analysis"
3. Selects appropriate checklist (e.g., "Warren Buffett's Investment Criteria")
4. Navigates through questions one by one:
   - Reads question (potentially uses focus mode/read aloud)
   - Researches answer (currently external to platform)
   - Records findings and evaluation
   - Moves to next question
5. Completes session and reviews summary
6. Makes investment decision based on analysis

### Current Pain Points:
- **Research Gap**: Users leave platform to research, losing context
- **Note Organization**: Research notes mixed with final answers
- **Document Access**: Hard to quickly access relevant company docs
- **Time Management**: No visibility into research time per question
- **Context Loss**: No connection between related questions/documents

## Technical Notes

### Styling System:
- Uses CSS custom properties for theming
- Responsive design with mobile optimizations
- Animation system for smooth transitions
- Focus states for accessibility

### JavaScript Features:
- Speech synthesis for accessibility
- Keyboard shortcuts for power users
- Dynamic UI state management
- Smooth scrolling and animations

### Integration Points:
- **AI Service**: LLM integration for question analysis
- **Document System**: Company document management
- **Analytics**: Research time and progress tracking
- **Portfolio Integration**: Investment decision recording

---

*Last Updated: January 2025*
*Version: 1.0*