# Question Anchoring: Focus Mode for Free Research

**Date:** 2026-02-15
**Status:** Approved
**Prototype:** `docs/design_proposal_question_anchoring.html`

## Problem

In the Free Research module, all questions are presented as a flat, equal-weight list. When a user expands a question to write notes or use AI tools, the question text scrolls away and there's no persistent "this is what I'm investigating" signal. Users lose focus, especially during longer research sessions.

## Solution: Focus Mode

A dedicated Focus Mode that isolates a single question, hides all others, and provides linear navigation between questions. Activated explicitly by clicking a "Focus" button on any question card header.

### UX Flow

1. **Normal mode** — Existing behavior: flat list of question cards, click to expand/collapse.
2. **Enter Focus Mode** — Click the "Focus" button (crosshair icon) on any question card header.
3. **Focus Mode active:**
   - All other question cards collapse and hide (animated).
   - The focused card auto-expands with a green accent highlight.
   - A sticky toolbar appears at the top showing the focused question text + "Exit Focus (Esc)" button.
   - The "Add Question" section and "Complete Step" section hide.
   - Navigation: Prev/Next buttons at the bottom of the card body, plus dot indicators showing position and status of all questions.
   - Keyboard: `Esc` to exit, `ArrowLeft`/`ArrowRight` to navigate.
4. **Exit Focus Mode** — Click "Exit Focus" in the toolbar, press `Esc`, or (future) click outside the card. Returns to normal flat list view.

### Visual Design

- **Focus button:** `fr-focus-btn` — small pill button with crosshair icon, appears in each card header. On hover, turns accent-green with subtle shadow.
- **Focused card:** `fr-focused` — accent-green left border (5px), elevated shadow, green-tinted header gradient. Expand chevron hidden (card is always expanded).
- **Hidden cards:** `fr-hidden` — animated collapse via `opacity: 0`, `max-height: 0`, with staggered transition timing.
- **Sticky toolbar:** `fr-focus-toolbar` — dark slate bar (primary-800) with crosshair icon, "Focused on:" label, question text (truncated with ellipsis), and exit button with `Esc` keyboard hint.
- **Focus navigation:** `fr-focus-nav` — bottom bar with Prev/Next buttons and dot indicators. Dots show current position (accent-green, scaled up) and answered status (green dot).
- **Body state:** `body.focus-mode-active` — slightly darker background (#f0f1f5) for subtle dimming effect.

### Sidebar Behavior

- Sidebar keeps existing layout: Company Info + Stats, Model Questions Library, Quick Actions.
- No new "Questions Map" section. The sidebar question map from the prototype is dropped.
- In focus mode, clicking a question in Model Questions still inserts it normally (it enters the list but doesn't auto-focus).

### Checklist Module

The checklist module already shows one question at a time with linear navigation. No Focus Mode needed there — it's structurally equivalent. If the question scrolls away during long note-taking, a future enhancement could add a sticky question header (Approach A from the prototype), but that's out of scope for this design.

## Scope

- **In scope:** Focus Mode for `free_research_step.html` — CSS + JS only, no backend changes.
- **Out of scope:** Checklist module sticky header, sidebar question map, any model/route changes.

## Additional Change

- `position-btn` border-radius updated from `--radius-sm` (4px) to `--radius-md` (8px) platform-wide for a slightly rounder button style.
