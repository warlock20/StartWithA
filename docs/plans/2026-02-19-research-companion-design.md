# Research Companion — Design Document

> "The best investors don't have better data. They have better thinking."

## Problem

Three pain points, equally important:

1. **Research happens outside the app** — findings from browsers, LLMs, PDFs don't flow back into the structured workflow
2. **Research lacks depth/rigor** — no active challenge of thesis, no counter-evidence, no gap detection
3. **Data gathering is manual** — too much time on collection, not enough on analysis

## Core Principle: Facts, Not Opinions

The companion surfaces data, highlights gaps, and shows patterns from the user's own history. It never tells the user what to think.

- If the user asks for an opinion, the companion warns: "Forming the investment opinion is your job — that's where your edge comes from. I can show you what the data says and what you might be missing."
- The companion shows what's missing, not what to conclude
- Counter-evidence is presented as facts to consider, not as recommendations

## Architecture

### Argos Enrichment (Context Engine)

The existing Argos intelligence engine becomes the foundation. It already loads: company, current step, research questions, findings, flags, thesis evolution.

**What's missing and needs to be added:**

| Data Source | What It Adds |
|---|---|
| Mistake Log | Past mistakes for this company/sector — patterns the user has fallen into before |
| Journal Entries | Decision journal entries related to this company/sector — prior reasoning and outcomes |
| Common Patterns | Recurring mistakes in this sector, biases detected in similar decisions, cross-company learnings |

This enriched context feeds every companion feature.

### Component Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                      Research Companion                           │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    User-Facing Features                      │  │
│  │                                                              │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌──────────────────────┐   │  │
│  │  │  Research    │ │   Live      │ │  Counter-Evidence    │   │  │
│  │  │  Brief      │ │  Companion  │ │  Agent               │   │  │
│  │  │             │ │  (chat)     │ │                      │   │  │
│  │  │ Pre-session │ │ Surfaces    │ │ Finds contradicting  │   │  │
│  │  │ what to     │ │ facts, gaps │ │ facts for key        │   │  │
│  │  │ look for    │ │ warns on    │ │ findings             │   │  │
│  │  │             │ │ opinion-ask │ │                      │   │  │
│  │  └──────┬──────┘ └──────┬──────┘ └──────────┬───────────┘   │  │
│  │         │               │                    │               │  │
│  │  ┌──────┴──────┐ ┌──────┴──────────────────────────────┐     │  │
│  │  │  Session    │ │  Quick-Capture API + Bookmarklet    │     │  │
│  │  │  Wrap-Up    │ │  Bridge for external research       │     │  │
│  │  └──────┬──────┘ └──────┬──────────────────────────────┘     │  │
│  └─────────┼───────────────┼────────────────────────────────────┘  │
│            ▼               ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │          ArgosService (app/services/argos/core.py)           │  │
│  │                 THE SINGLE ORCHESTRATOR                      │  │
│  │                                                              │  │
│  │  DATA GATHERING (existing + enriched):                       │  │
│  │  ├── check()                    ← existing entry point       │  │
│  │  ├── _gather_mistake_matches()  ← existing                  │  │
│  │  ├── _gather_loss_patterns()    ← existing                  │  │
│  │  ├── _gather_journal_insights() ← NEW                       │  │
│  │  ├── _gather_pattern_warnings() ← NEW                       │  │
│  │  └── _score_with_llm()          ← existing                  │  │
│  │                                                              │  │
│  │  COMPANION FEATURES (new):                                   │  │
│  │  ├── build_research_context()   ← assembles full context    │  │
│  │  ├── generate_brief()           ← pre-session brief         │  │
│  │  ├── ask_companion()            ← facts-only chat           │  │
│  │  ├── generate_counter_evidence()← challenges findings       │  │
│  │  └── wrap_up_session()          ← session summary           │  │
│  │                                                              │  │
│  └──────────────────────────┬──────────────────────────────────┘  │
│                             │                                     │
│  ┌──────────────────────────┴──────────────────────────────────┐  │
│  │                 Existing Infrastructure                       │  │
│  │                                                              │  │
│  │  AIService (Gemini/Claude/OpenAI) │ Celery (async tasks)     │  │
│  │  ResearchProject model + workflow │ EmbeddingStore (pgvector) │  │
│  │  Prompt Templates (YAML)          │ WorkSession + TimeTracker │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## Features

### 1. Argos Enrichment (Context Engine)

**What:** Extend the existing Argos intelligence engine to include mistake log, journal entries, and cross-company patterns in its context assembly.

**How:**
- Query MistakeLog entries where `company_id` matches or `sector_id` matches the current research company's sector
- Query DecisionJournal entries for the same company/sector
- Query PatternRecognition for recurring patterns in this sector
- Assemble into a structured context object that all companion features consume

**New data in context:**
```
{
  "company": { ... existing ... },
  "research_project": { ... existing ... },
  "history": {
    "mistakes": [{ "description", "lesson", "date", "company/sector" }],
    "journal_entries": [{ "decision_type", "reasoning", "outcome", "date" }],
    "patterns": [{ "pattern_type", "description", "frequency", "last_seen" }]
  }
}
```

### 2. Research Brief

**What:** Before starting a research step, the AI generates a brief grounded in the enriched Argos context.

**Output format:**
- What you're trying to answer (research questions for this step)
- What you already know (prior findings, step notes)
- 3 specific things to look for in the next 30 minutes
- Warnings from your history ("You've underestimated competitive threats in this sector 3 times before — pay attention to moat durability")

**Trigger:** User clicks "Start Session" or opens a research step.

**Implementation:** New prompt template `companion/research_brief.yaml` + route in research workflow. Async via Celery if context assembly is heavy.

### 3. Live Companion (Facts-Only Chat)

**What:** During a research session, the user can ask the companion questions. The companion answers using the enriched Argos context — always with facts, never opinions.

**Behavior rules:**
- Surfaces information: "Question 3 has zero findings. Your template suggests looking at customer switching costs, pricing power history, and market share trends."
- Highlights gaps: "You have 4 findings for competitive position but none address the pricing power sub-question."
- Shows history: "Your mistake log shows 2 past instances of ignoring margin compression in this sector."
- **Warns on opinion-seeking:** If the user asks "Should I invest?" or "Is this a good company?" → "Forming the investment opinion is your job — that's where your edge comes from. I can show you what the data says and what you might be missing."

**Implementation:** Chat-style UI within the research project dashboard. Each message sends context + user question to AIService. Conversation history maintained per session.

### 4. Counter-Evidence Agent

**What:** For each key finding the user adds, the AI actively searches for contradicting evidence.

**How it works:**
- User adds a finding: "ASML has 90% market share in EUV lithography"
- Companion responds: "Counter-evidence to consider: (1) Chinese competitors SMEE are developing alternatives, (2) Intel and Samsung have reduced EUV tool orders in Q3 2025, (3) Some advanced chips are exploring non-EUV approaches. Sources to verify: [specific search suggestions]"

**Not:** "Your finding is wrong" (opinion). Instead: "Here are facts that could challenge this finding" (information).

**Implementation:** New prompt template `companion/counter_evidence.yaml`. Triggered automatically when a finding is saved, runs async via Celery. Results shown as a "Counter-Evidence" panel next to the finding.

### 5. Quick-Capture API + Bookmarklet

**What:** A lightweight bridge for capturing research findings from anywhere (browser, LLM conversations, PDFs) into the right research project and step.

**API:** `POST /research/api/capture`
```json
{
  "text": "Selected text or pasted content",
  "url": "https://source-page.com (optional)",
  "project_id": "optional — if known",
  "step_index": "optional — if known"
}
```

**Bookmarklet:** JavaScript snippet for the browser toolbar. Click it on any page → captures page title, URL, selected text → sends to capture endpoint → tiny popup to pick project/step.

**New model:** `ResearchCapture` — stores captures before they're assigned to a step. Fields: `text`, `url`, `source_title`, `project_id` (nullable), `step_index` (nullable), `status` (unassigned/assigned/dismissed), `captured_at`.

**In-app:** "Research Clipboard" panel in project dashboard where unassigned captures land. User drags them to the right step or dismisses.

### 6. Session Wrap-Up

**What:** At the end of a research session, the AI summarizes what happened.

**Output format:**
- Time spent this session
- Questions addressed (and which remain open)
- Strongest finding this session
- Biggest remaining gap
- Suggested focus for next session
- Counter-evidence that still needs verification

**Trigger:** User clicks "End Session" or navigates away from research project (with a prompt).

**Implementation:** New prompt template `companion/session_wrapup.yaml`. Uses session's findings, time data, and research question state. Stored on the ResearchProject as part of session history.

## New Files

| File | Purpose |
|---|---|
| `app/services/ai/prompts/companion/research_brief.yaml` | Research brief prompt template |
| `app/services/ai/prompts/companion/counter_evidence.yaml` | Counter-evidence prompt template |
| `app/services/ai/prompts/companion/session_wrapup.yaml` | Session wrap-up prompt template |
| `app/services/ai/prompts/companion/live_companion.yaml` | Live companion chat prompt (with opinion-warning rules) |
| `app/models/research_capture.py` | ResearchCapture model for quick-capture |
| `app/research_workflow/companion_routes.py` | Routes for companion features |
| `app/research_workflow/templates/companion_panel.html` | UI for companion sidebar/panel |
| `app/research_workflow/templates/research_clipboard.html` | UI for captures clipboard |
| `app/static/js/bookmarklet.js` | Bookmarklet source |

## Files Modified

| File | Changes |
|---|---|
| `app/services/argos/core.py` | Add companion methods: `build_research_context()`, `generate_brief()`, `ask_companion()`, `generate_counter_evidence()`, `wrap_up_session()`. Add gathering methods: `_gather_journal_insights()`, `_gather_pattern_warnings()` |
| `app/services/argos/config.py` | Add `JOURNAL_INSIGHT` and `PATTERN_WARNING` to `InsightCategory` enum and `CONTEXT_RULE_MATRIX` |

## Models Modified

| Model | Changes |
|---|---|
| `ResearchProject` | Add `session_history` (JSON array — stores wrap-up summaries per session) |

## UI Integration Strategy (Revised Feb 2026)

### Design Principle: Invisible Infrastructure

The companion is NOT a chatbot. It extends existing UI surfaces with proactive intelligence. No new floating widgets, no separate chat panel. The companion enriches what already exists.

### Two-Layer Cost Model

| Layer | Cost | Trigger | What |
|-------|------|---------|------|
| **Free layer** | Zero tokens (DB queries) | Auto on page load | Pattern warnings, journal insights |
| **Token layer** | LLM call | User clicks button | Research brief, enriched AI responses, counter-evidence |

`_gather_journal_insights()` and `_gather_pattern_warnings()` are pure DB queries — they run on every page load for free.

### 4 Integration Surfaces

#### Surface 1: Project Dashboard — Companion Alerts Sidebar Card
- **Location:** Right sidebar, between Key Findings and Quick Actions
- **Content:** Pattern warnings + journal insights (free layer, auto-loaded)
- **Format:** Card with warning items styled like `_warnings-widget.css` severity pattern
- **Template:** `_companion_alerts.html` partial included in `project_dashboard.html`

#### Surface 2: Checklist Step — Warning Banner + Enriched AI
- **Location:** Top of main content area (warning banner), inside AI Research Assistant responses
- **Warning banner:** Auto-loads free pattern warnings on page load
- **Enriched AI:** When user clicks Challenge/Elaborate/Fact-Check, existing `AIResearchAssistant` sends additional companion context to the AI endpoint
- **Template:** `_companion_banner.html` partial included in `research_step.html`

#### Surface 3: Free Research Step — Warning Banner + Enriched AI
- **Location:** Existing `free-research-warning` banner area at top
- **Warning banner:** Auto-loads free pattern warnings (follows existing warning banner pattern)
- **Enriched AI:** Per-question inline AI tools get companion context injected
- **Template:** `_companion_banner.html` partial included in `free_research_step.html`

#### Surface 4: Generic Step (execute_step.html) — Warning Banner
- **Location:** Top of main content area
- **Content:** Pattern warnings + journal insights (free layer)
- **Template:** `_companion_banner.html` partial

### What Was Removed
- **Floating chat widget** — deferred to future. The Intercom-style chat prototype (`docs/companion_ui_prototype.html`) is kept as a reference for later.
- **Separate companion panel** — companion is invisible infrastructure, not a UI component
- **Full chat interface** — user interacts via existing AI tools, not a new chat input

### New Endpoint: Lightweight Warnings
`GET /companion/<project_id>/warnings` — returns pattern warnings + journal insights from DB (zero token cost). Called via AJAX on page load for all 4 surfaces.

## What's Deferred

| Feature | Why |
|---|---|
| Finding Quality Scoring | Too tricky — subjective, risk of false confidence |
| Browser Extension | Start with bookmarklet, upgrade if adoption is high |
| CrewAI Integration | Existing AI service sufficient for now; revisit for "one-click deep research" later |
| Broker MCP/API | Improve CSV import first; broker sync when paying users demand it |

## Decision Log

| Decision | Reasoning |
|---|---|
| Extend Argos, don't rebuild | Argos already assembles company/research context — just needs mistake/journal/pattern data. Companion features are new methods on ArgosService, not a separate service. One orchestrator, one context assembly, no duplication. |
| Facts-only companion | Aligns with moat: "better thinking, not better data." Companion surfaces information, user forms opinions |
| Counter-evidence over quality scoring | Counter-evidence provides actionable facts; quality scoring is subjective and deferred |
| Bookmarklet over browser extension | Zero friction to build, no app store approval, proves the concept before investing in an extension |
| No new frameworks (CrewAI, LangGraph) | Existing AIService + Celery is sufficient; avoid dependency bloat |
