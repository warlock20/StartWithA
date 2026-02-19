# Research Focus Dashboard — Design Document

> **Goal:** Help the user focus on research by answering "What should I work on right now?" every time they open the app.

## Problem

- Too many active research projects with no prioritization
- No urgency or nudge to continue stalled projects
- Psychology says 2-3 deep projects is the cognitive limit — the system should enforce focus, not just inform it
- Projects sit idle for weeks with no signal to either pick them up or kill them

## Solution Overview

Two enhancements to existing pages (no new pages):

1. **Main Dashboard** (`/dashboard`) — a "Research Focus" card that recommends the ONE project to work on next, with runners-up and warnings
2. **My Projects** (`/research/workflow/my-projects`) — priority-scored ordering of active projects with sort controls and over-limit visual treatment

Both powered by a **priority scoring algorithm** with admin-tunable parameters.

---

## 1. Priority Scoring Algorithm

Computes a score (0-100) per active `ResearchProject`. Higher = work on this next.

### Factors

| Factor | Default Weight | Source Fields | Logic |
|--------|---------------|---------------|-------|
| **Momentum** | 40% | `last_worked_at` | Exponential decay. Recent work = high score. Half-life: 3 days |
| **Proximity to done** | 25% | `progress_percentage` | Concave curve rewarding near-completion. 80% done scores much higher than 50% |
| **Staleness pressure** | 20% | `last_worked_at`, `created_at` | Bell curve peaking at ~10 days idle (nudge). Drops after 14+ days (stale) |
| **Investment signal** | 15% | `green_flags`, `red_flags`, `WorkSession.needs_followup` | More green flags = promising. Pending followups = urgent |

### Formula

```
momentum_score    = decay_curve(days_idle, half_life=settings.momentum_half_life_days) * settings.weight_momentum
proximity_score   = (progress_pct / 100) ^ 0.7 * settings.weight_proximity
staleness_score   = bell_curve(days_idle, peak=settings.staleness_peak_days) * settings.weight_staleness
signal_score      = normalize(green_flags - red_flags + followup_urgency) * settings.weight_signal

total = momentum + proximity + staleness + signal
```

### Recommendation Labels

- Score > 70: **"Continue next"**
- Score 40-70: **"Needs attention"**
- Score < 40: **"Consider pausing"**

### Special Rules

- **Active project limit (admin-set, default 3):** Over-limit triggers a warning on the dashboard
- **Stale project warning:** Idle > `stale_warning_days` with < `stale_warning_min_progress`% progress suggests moving to Too Hard
- **Tie-breaking:** Within 5 points, higher progress % wins

---

## 2. Tunable Parameters

All parameters are admin-configurable via the `ResearchSettings` model. No admin UI in the first increment — tuned via database, admin UI added later.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `active_project_limit` | 3 | Max projects before over-limit warning |
| `weight_momentum` | 40 | % weight for momentum factor |
| `weight_proximity` | 25 | % weight for proximity-to-done |
| `weight_staleness` | 20 | % weight for staleness pressure |
| `weight_signal` | 15 | % weight for investment signal |
| `momentum_half_life_days` | 3 | Decay speed for momentum (lower = more aggressive) |
| `staleness_peak_days` | 10 | Day count where staleness nudge is strongest |
| `stale_warning_days` | 14 | Days idle before "consider killing" suggestion |
| `stale_warning_min_progress` | 30 | Progress % below which stale projects get kill suggestion |

**Constraint:** Weights must sum to 100.

---

## 3. Dashboard "Research Focus" Card

Replaces the current simple active projects list on `/dashboard`.

### Layout

```
┌─────────────────────────────────────────────────────┐
│  RESEARCH FOCUS                                     │
│                                                     │
│  Pick up ASML Holding                               │
│  Competitive Analysis step — 62% complete           │
│  Last worked: 2 days ago · 4.2 hrs invested         │
│                                                     │
│  [Continue Research]                                 │
│                                                     │
│  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄  │
│  Also active:                                       │
│  2. Costco — Thesis Writing · 35% · idle 12d        │
│  3. Rational AG — Kill Checklist · 10% · idle 4d    │
│                                                     │
│  5 active projects — your focus limit is 3.         │
│  Consider pausing or killing 2.                     │
└─────────────────────────────────────────────────────┘
```

### States

- **Has active projects:** Hero recommendation + runners-up + optional warnings
- **Zero active projects:** "No active research. Check your Idea Inbox (X ideas waiting)."
- **Over limit:** Warning banner with link to My Projects

---

## 4. My Projects Page Enhancements

Changes to the Active Research tab on `/research/workflow/my-projects`.

- **Default sort: Priority Score** (replaces `last_worked_at desc`)
- **Sort dropdown:** Priority (default), Last Worked, Progress %, Newest First
- **Priority badge** on each project card: "Continue next" / "Needs attention" / "Consider pausing"
- **Over-limit dimming:** Projects beyond the `active_project_limit` get a subtle dimmed treatment with hint text

---

## 5. Data Model

### New: `ResearchSettings`

```python
class ResearchSettings(db.Model):
    __tablename__ = 'research_settings'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), unique=True)

    # Focus limits
    active_project_limit = Column(Integer, default=3)

    # Scoring weights (must sum to 100)
    weight_momentum = Column(Integer, default=40)
    weight_proximity = Column(Integer, default=25)
    weight_staleness = Column(Integer, default=20)
    weight_signal = Column(Integer, default=15)

    # Tuning knobs
    momentum_half_life_days = Column(Integer, default=3)
    staleness_peak_days = Column(Integer, default=10)
    stale_warning_days = Column(Integer, default=14)
    stale_warning_min_progress = Column(Integer, default=30)
```

One row per user. Get-or-create pattern (same as `ResearchMetrics`).

### Existing models used (no changes)

- `ResearchProject` — `last_worked_at`, `progress_percentage`, `green_flags`, `red_flags`, `created_at`, `status`, `current_step_index`
- `WorkSession` — `needs_followup`
- `ResearchTemplate` — `workflow_steps` (for current step name)

---

## 6. Service Architecture

### New: `ResearchPriorityService` (`app/services/research_priority.py`)

```
ResearchPriorityService
├── score_project(project, settings) -> ProjectScore
│     Computes all four subscores
│     Returns: { total, momentum, proximity, staleness, signal, label }
│
├── rank_projects(user) -> List[RankedProject]
│     Fetches active projects + user settings
│     Returns sorted list with scores + over_limit flag
│
├── get_focus_recommendation(user) -> FocusRecommendation
│     Calls rank_projects, picks #1
│     Returns: { hero_project, runners_up, warnings[] }
│
└── get_recommendation_label(score) -> str
      Maps score to "Continue next" / "Needs attention" / "Consider pausing"
```

Scores computed on-the-fly per page load. No historical tracking (not needed now).

### Integration Points

| File | Change |
|------|--------|
| `app/models/research.py` | Add `ResearchSettings` model |
| `app/services/research_priority.py` | New service (scoring logic) |
| `app/dashboard/routes.py` | Call `get_focus_recommendation()`, pass to template |
| `app/dashboard/templates/dashboard.html` | New "Research Focus" card section |
| `app/research_workflow/project_management_routes.py` | Call `rank_projects()`, accept `?sort=priority` |
| `app/research_workflow/templates/projects_dashboard.html` | Sort dropdown, priority badges, over-limit dimming |
| DB migration | Add `research_settings` table |

---

## 7. Deferred (Future Increments)

- **Admin settings UI** — page to adjust weights and knobs visually (slider group with sum-to-100 constraint)
- **Notification/email nudges** — "You haven't touched Costco in 12 days" reminders
- **Historical score tracking** — track scores over time for trend analysis
- **Per-project user override** — "Pin this as my #1 regardless of algorithm"
- **Conviction score** — user-set evolving excitement/conviction per project (pre-decision)
