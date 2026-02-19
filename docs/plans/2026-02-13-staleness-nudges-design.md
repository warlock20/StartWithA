# Staleness Nudges — Design Document

**Goal:** Surface stale research projects on the Company Research page with escalating urgency, prompting the user to either resume work or move the project to Too Hard.

**Approach:** Two-tier system — soft visual flag in the table at X days idle, action prompt in a new alerts strip at Y days idle + low progress.

---

## 1. Header Architecture: `dashboard-alerts-strip`

The `dashboard-header-card` currently mixes metrics and warnings. New structure:

```
dashboard-header-card
├── dashboard-header          (title + buttons — unchanged)
├── dashboard-metrics-strip   (metrics ONLY — no warnings)
└── dashboard-alerts-strip    (NEW — warnings, nudges, alerts)
```

- Move the existing over-limit warning out of `dashboard-metrics-strip` into `dashboard-alerts-strip`
- The alerts strip only renders when alerts exist — no empty space when healthy
- Reusable: any page using `dashboard-header-card` can add alerts
- CSS in `_dashboard.css` — simple vertical stack, no grid

### Collapsed pattern

The strip shows one summary line with the most urgent alert + a count:

```
⚠  ASML idle 25d · 15% done — Still pursuing?  [Too Hard] [I'll work on it]   +2 more  [Show all]
```

- Most urgent Tier 2 project shown (highest `days_idle`)
- "+N more" includes other Tier 2 nudges + over-limit warning
- "Show all" expands in-place to reveal all alerts stacked vertically
- Single alert: no count, no "Show all"
- Zero alerts: strip doesn't render

---

## 2. Two-Tier Staleness Logic

### Tier 1 — "Getting stale" (soft flag)

- **Trigger:** `days_idle >= stale_warning_days` (existing setting, default 14)
- **No progress gate** — any idle project qualifies
- **Surface:** Amber "Idle Xd" badge appended to the Status column in the Tabulator table
- **Passive** — awareness only, no action needed

### Tier 2 — "Decision needed" (action prompt)

- **Trigger:** `days_idle >= stale_nudge_days` (new setting, default 21) AND `progress < stale_warning_min_progress` (existing, default 30%)
- **Rationale:** High-progress + idle = needs a nudge to resume (Tier 1 handles it). Low-progress + very idle = likely stuck, needs a decision.
- **Surface:** Alert card in `dashboard-alerts-strip` with action buttons
- **Actions:**
  - "Move to Too Hard" → navigates to existing `mark_too_hard` route
  - "I'll work on it" → AJAX POST to `/projects/<id>/touch`, resets idle clock

---

## 3. Data Model

**New column on `ResearchSettings`:**

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `stale_nudge_days` | Integer | 21 | Tier 2 threshold (days idle before action prompt) |

Everything else reuses existing fields:
- `stale_warning_days` (default 14) — Tier 1 threshold
- `stale_warning_min_progress` (default 30) — Tier 2 progress gate

---

## 4. Backend Changes

### Route: `my_projects()` in `project_management_routes.py`

Add `staleness_tier` to each `active_data` dict:
- `0` = healthy
- `1` = getting stale (days_idle >= stale_warning_days)
- `2` = decision needed (days_idle >= stale_nudge_days AND progress < stale_warning_min_progress)

Build an `alerts` list for the template:
- Tier 2 staleness nudges (sorted by days_idle desc)
- Over-limit warning (if active_count > project_limit)

Pass `alerts` and `alerts_json` to the template.

### New route: `POST /projects/<id>/touch`

- Updates `last_worked_at = now_utc()` on the project
- Returns JSON `{ "ok": true }` for AJAX
- Authorization check: project must belong to current user

---

## 5. Frontend Changes

### Template: `projects_dashboard.html`

- Remove `research-focus-warning--full-width` from inside `dashboard-metrics-strip`
- Add `dashboard-alerts-strip` after `dashboard-metrics-strip` inside `dashboard-header-card`
- Collapsed/expanded toggle via JS (vanilla, no library)

### Tabulator: Status column formatter

Append idle badge when `staleness_tier >= 1`:
```
<span class="rcl-cell-badge rcl-cell-badge--active">active</span>
<span class="rcl-cell-badge rcl-cell-badge--idle">Idle 18d</span>
```

### AJAX: "I'll work on it" button

POST to `/projects/<id>/touch`, on success:
- Fade out the alert card
- Update the table row's `staleness_tier` to 0 (remove idle badge)
- Decrement the "+N more" count

---

## 6. CSS

- `dashboard-alerts-strip` in `_dashboard.css` — flex column, gap, border-top separator
- `dashboard-alert-card` — reuses `--warning-soft` background, flex row layout
- `dashboard-alert-card__actions` — inline buttons using existing `position-btn` class
- `rcl-cell-badge--idle` in `_research-command-center.css` — amber variant

---

## 7. Deferred

- Admin settings UI for `stale_nudge_days` (future)
- Staleness nudges on the main Dashboard page (future — currently only Company Research page)
- Staleness banner on individual project dashboard page (future)
