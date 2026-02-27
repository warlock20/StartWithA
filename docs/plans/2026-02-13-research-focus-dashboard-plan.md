# Research Focus Dashboard — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a priority scoring system that recommends which research project to work on next, surfaced on the main dashboard and My Projects page.

**Architecture:** New `ResearchSettings` model stores tunable scoring parameters per user. New `ResearchPriorityService` computes priority scores from existing `ResearchProject` fields (momentum, progress, staleness, investment signals). The dashboard route calls the service and passes a `FocusRecommendation` to the template. My Projects page gets priority-based sorting and badges.

**Tech Stack:** Flask, SQLAlchemy, Flask-Migrate (Alembic), Jinja2, vanilla JS (Tabulator on My Projects)

**Design doc:** `docs/plans/2026-02-13-research-focus-dashboard-design.md`

---

## Task 1: Add `ResearchSettings` Model

**Files:**
- Modify: `app/models/research.py` (append after `ResearchMetrics` class, ~line 433)
- Modify: `app/models/__init__.py` (add import)

**Step 1: Add the model class**

Add to `app/models/research.py` after the `ResearchMetrics` class:

```python
class ResearchSettings(db.Model):
    """
    Per-user tunable parameters for the research priority scoring algorithm.
    One row per user, created with defaults on first access (get-or-create).
    """
    __tablename__ = 'research_settings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)

    # Focus limits
    active_project_limit = db.Column(db.Integer, default=3)

    # Scoring weights (must sum to 100)
    weight_momentum = db.Column(db.Integer, default=40)
    weight_proximity = db.Column(db.Integer, default=25)
    weight_staleness = db.Column(db.Integer, default=20)
    weight_signal = db.Column(db.Integer, default=15)

    # Tuning knobs
    momentum_half_life_days = db.Column(db.Integer, default=3)
    staleness_peak_days = db.Column(db.Integer, default=10)
    stale_warning_days = db.Column(db.Integer, default=14)
    stale_warning_min_progress = db.Column(db.Integer, default=30)

    def __repr__(self):
        return f'<ResearchSettings for User {self.user_id}>'

    @staticmethod
    def get_or_create(user_id):
        """Get existing settings or create with defaults."""
        settings = ResearchSettings.query.filter_by(user_id=user_id).first()
        if not settings:
            settings = ResearchSettings(user_id=user_id)
            db.session.add(settings)
            db.session.commit()
        return settings
```

**Step 2: Register the import**

In `app/models/__init__.py`, find the research imports line:

```python
from .research import (ChecklistAnalysis, ResearchProject, WorkSession, ...)
```

Add `ResearchSettings` to that import tuple.

**Step 3: Create the migration**

Run:
```bash
cd /home/warlock20/dev/investment-checklist && venv/bin/flask db migrate -m "add research_settings table"
```

**Step 4: Apply the migration**

Run:
```bash
cd /home/warlock20/dev/investment-checklist && venv/bin/flask db upgrade
```

**Step 5: Verify**

Run:
```bash
cd /home/warlock20/dev/investment-checklist && venv/bin/python -c "
from app import create_app, db
from app.models import ResearchSettings
app = create_app()
with app.app_context():
    print('Table exists:', db.engine.has_table('research_settings'))
    print('Columns:', [c.name for c in ResearchSettings.__table__.columns])
"
```

Expected: `Table exists: True` and all column names printed.

**Step 6: Commit**

```bash
git add app/models/research.py app/models/__init__.py migrations/versions/
git commit -m "feat: add ResearchSettings model for priority scoring tunable parameters"
```

---

## Task 2: Build `ResearchPriorityService` — Scoring Logic

**Files:**
- Create: `app/services/research_priority.py`

**Step 1: Create the service file**

Create `app/services/research_priority.py`:

```python
"""
Research Priority Service

Computes priority scores (0-100) for active research projects to help
the user decide what to work on next. Higher score = work on this first.

Factors:
- Momentum (default 40%): Recent work = high score, exponential decay
- Proximity to done (default 25%): Concave curve rewarding near-completion
- Staleness pressure (default 20%): Bell curve peaking at ~10 days idle
- Investment signal (default 15%): Green/red flags + pending followups
"""

import math
from dataclasses import dataclass, field
from app.utils.time_utils import now_utc, ensure_timezone_aware


@dataclass
class ProjectScore:
    """Score breakdown for a single research project."""
    project: object
    total: float = 0.0
    momentum: float = 0.0
    proximity: float = 0.0
    staleness: float = 0.0
    signal: float = 0.0
    label: str = ''
    days_idle: int = 0
    is_stale_warning: bool = False


@dataclass
class FocusRecommendation:
    """The complete recommendation for the dashboard."""
    hero: ProjectScore = None
    runners_up: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    active_count: int = 0
    project_limit: int = 3


class ResearchPriorityService:

    @staticmethod
    def score_project(project, settings):
        """
        Compute priority score for a single project.

        Args:
            project: ResearchProject instance (status must be 'active')
            settings: ResearchSettings instance with tunable parameters

        Returns:
            ProjectScore with total (0-100) and subscores
        """
        score = ProjectScore(project=project)

        # --- Days idle ---
        if project.last_worked_at:
            last_worked_aware = ensure_timezone_aware(project.last_worked_at)
            delta = now_utc() - last_worked_aware
            score.days_idle = max(0, delta.days)
        else:
            # Never worked on — use created_at
            created_aware = ensure_timezone_aware(project.created_at)
            delta = now_utc() - created_aware
            score.days_idle = max(0, delta.days)

        # --- Momentum (exponential decay) ---
        # Half-life: after N days, momentum halves. e.g., half_life=3:
        #   0 days -> 1.0, 3 days -> 0.5, 6 days -> 0.25
        half_life = max(1, settings.momentum_half_life_days)
        decay = math.exp(-0.693 * score.days_idle / half_life)  # ln(2) ≈ 0.693
        score.momentum = decay * settings.weight_momentum

        # --- Proximity to done (concave curve) ---
        # (progress/100)^0.7 — rewards near-completion disproportionately
        # 80% -> 0.86, 50% -> 0.62, 20% -> 0.30
        progress_pct = project.progress_percentage or 0.0
        proximity_raw = (progress_pct / 100.0) ** 0.7 if progress_pct > 0 else 0.0
        score.proximity = proximity_raw * settings.weight_proximity

        # --- Staleness pressure (bell curve) ---
        # Peaks at staleness_peak_days, drops off on both sides.
        # Uses a Gaussian centered at peak_days with sigma = peak_days/2
        peak = max(1, settings.staleness_peak_days)
        sigma = peak / 2.0
        staleness_raw = math.exp(-0.5 * ((score.days_idle - peak) / sigma) ** 2)
        score.staleness = staleness_raw * settings.weight_staleness

        # --- Investment signal ---
        # green_flags - red_flags + followup urgency, normalized to [0, 1]
        green_count = len(project.green_flags) if project.green_flags else 0
        red_count = len(project.red_flags) if project.red_flags else 0

        # Check for pending followups in recent work sessions
        followup_count = 0
        if project.work_sessions:
            followup_count = project.work_sessions.filter_by(needs_followup=True).count()

        # Raw signal: green flags are positive, red flags reduce but don't go below 0,
        # followups add urgency
        signal_raw = max(0, green_count - red_count) + (followup_count * 2)
        # Normalize: cap at 10 signals for full score
        signal_normalized = min(1.0, signal_raw / 10.0)
        score.signal = signal_normalized * settings.weight_signal

        # --- Total ---
        score.total = round(score.momentum + score.proximity + score.staleness + score.signal, 1)

        # --- Label ---
        score.label = ResearchPriorityService.get_recommendation_label(score.total)

        # --- Stale warning ---
        score.is_stale_warning = (
            score.days_idle > settings.stale_warning_days
            and progress_pct < settings.stale_warning_min_progress
        )

        return score

    @staticmethod
    def get_recommendation_label(total_score):
        """Map score to a human-readable recommendation label."""
        if total_score > 70:
            return 'Continue next'
        elif total_score >= 40:
            return 'Needs attention'
        else:
            return 'Consider pausing'

    @staticmethod
    def rank_projects(user):
        """
        Score and rank all active projects for a user.

        Args:
            user: User instance

        Returns:
            List of ProjectScore, sorted by total desc (tie-break: progress %)
        """
        from app.models import ResearchProject, ResearchSettings

        settings = ResearchSettings.get_or_create(user.id)

        active_projects = user.research_projects.filter(
            ResearchProject.status.in_(['active'])
        ).all()

        scored = [
            ResearchPriorityService.score_project(p, settings)
            for p in active_projects
        ]

        # Sort by total score desc, tie-break by progress % desc
        scored.sort(key=lambda s: (s.total, s.project.progress_percentage or 0), reverse=True)

        return scored

    @staticmethod
    def get_focus_recommendation(user):
        """
        Build the complete focus recommendation for the dashboard.

        Args:
            user: User instance

        Returns:
            FocusRecommendation with hero project, runners-up, and warnings
        """
        from app.models import ResearchSettings

        settings = ResearchSettings.get_or_create(user.id)
        ranked = ResearchPriorityService.rank_projects(user)

        rec = FocusRecommendation(
            active_count=len(ranked),
            project_limit=settings.active_project_limit,
        )

        if ranked:
            rec.hero = ranked[0]
            rec.runners_up = ranked[1:]

        # --- Warnings ---
        if len(ranked) > settings.active_project_limit:
            over_by = len(ranked) - settings.active_project_limit
            rec.warnings.append({
                'type': 'over_limit',
                'message': f'{len(ranked)} active projects \u2014 your focus limit is {settings.active_project_limit}. Consider pausing or killing {over_by}.',
            })

        for s in ranked:
            if s.is_stale_warning:
                rec.warnings.append({
                    'type': 'stale_project',
                    'message': f'{s.project.subject_display_name} has been idle {s.days_idle} days with only {s.project.progress_percentage:.0f}% progress. Move to Too Hard?',
                    'project_id': s.project.id,
                })

        return rec
```

**Step 2: Verify the service loads without errors**

Run:
```bash
cd /home/warlock20/dev/investment-checklist && venv/bin/python -c "
from app import create_app
app = create_app()
with app.app_context():
    from app.services.research_priority import ResearchPriorityService, ProjectScore, FocusRecommendation
    print('Service imported successfully')
    print('Label for 75:', ResearchPriorityService.get_recommendation_label(75))
    print('Label for 50:', ResearchPriorityService.get_recommendation_label(50))
    print('Label for 30:', ResearchPriorityService.get_recommendation_label(30))
"
```

Expected:
```
Service imported successfully
Label for 75: Continue next
Label for 50: Needs attention
Label for 30: Consider pausing
```

**Step 3: Commit**

```bash
git add app/services/research_priority.py
git commit -m "feat: add ResearchPriorityService with scoring algorithm for project prioritization"
```

---

## Task 3: Integrate Scoring into Dashboard Route

**Files:**
- Modify: `app/dashboard/routes.py` (lines 12-118)

**Step 1: Add import and service call**

At the top of `app/dashboard/routes.py`, add to imports:

```python
from app.services.research_priority import ResearchPriorityService
```

**Step 2: Replace active projects query with scored recommendation**

In the `index()` function, find this block (lines 20-23):

```python
# Get the top 5 active research projects
active_projects = current_user.research_projects.filter_by(status='active')\
                                                .order_by(ResearchProject.last_worked_at.desc())\
                                                .limit(5).all()
```

Replace with:

```python
# Get prioritized research recommendation
focus_recommendation = ResearchPriorityService.get_focus_recommendation(current_user)
active_projects = [s.project for s in ([focus_recommendation.hero] + focus_recommendation.runners_up) if s]
```

**Step 3: Pass the recommendation to the template**

In the `return render_template(...)` call (line 94), add `focus_recommendation`:

```python
focus_recommendation=focus_recommendation,
```

Keep `active_projects_list=active_projects` and `active_projects_count=len(active_projects)` as they are (other parts of the dashboard still use them).

**Step 4: Verify the route loads**

Run the dev server and hit `/dashboard` — it should load without errors. The template won't show the new card yet (that's the next task), but the existing "Today's Priorities" section should still work since `active_projects_list` is still passed.

```bash
cd /home/warlock20/dev/investment-checklist && venv/bin/python -c "
from app import create_app
app = create_app()
with app.app_context():
    from app.services.research_priority import ResearchPriorityService
    from app.models import User
    user = User.query.first()
    if user:
        rec = ResearchPriorityService.get_focus_recommendation(user)
        print(f'Active: {rec.active_count}, Limit: {rec.project_limit}')
        if rec.hero:
            print(f'Hero: {rec.hero.project.subject_display_name} (score: {rec.hero.total})')
        for r in rec.runners_up:
            print(f'  Runner-up: {r.project.subject_display_name} (score: {r.total})')
        for w in rec.warnings:
            print(f'  Warning: {w[\"message\"]}')
    else:
        print('No users found')
"
```

**Step 5: Commit**

```bash
git add app/dashboard/routes.py
git commit -m "feat: integrate ResearchPriorityService into dashboard route"
```

---

## Task 4: Build the "Research Focus" Card in Dashboard Template

**Files:**
- Modify: `app/dashboard/templates/dashboard.html` (~lines 92-125)

**Context:** The current "Today's Priorities" section (lines 95-112) shows a generic list of active projects. We replace it with a structured "Research Focus" card that shows the hero recommendation, runners-up, and warnings.

**Step 1: Replace the "Today's Priorities" research section**

Find the block inside the priorities section that loops over `active_projects_list` (lines 98-111):

```html
{% if active_projects_list %}
{% for project in active_projects_list[:3] %}
<div class="priority-task">
    ...
</div>
{% endfor %}
{% endif %}
```

Replace with:

```html
<!-- Research Focus Recommendation -->
{% if focus_recommendation and focus_recommendation.hero %}
<div class="research-focus-card">
    <div class="research-focus-header">
        <span class="research-focus-label">Research Focus</span>
    </div>
    <div class="research-focus-hero">
        <h3 class="research-focus-hero-title">
            Pick up {{ focus_recommendation.hero.project.subject_display_name }}
        </h3>
        <p class="research-focus-hero-meta">
            {% set current_step = focus_recommendation.hero.project.current_step %}
            {% if current_step %}{{ current_step.get('name', 'Step ' ~ (focus_recommendation.hero.project.current_step_index + 1)) }} — {% endif %}{{ focus_recommendation.hero.project.progress_percentage }}% complete
        </p>
        <p class="research-focus-hero-detail">
            {% if focus_recommendation.hero.days_idle == 0 %}
                Worked on today
            {% elif focus_recommendation.hero.days_idle == 1 %}
                Last worked: yesterday
            {% else %}
                Last worked: {{ focus_recommendation.hero.days_idle }}d ago
            {% endif %}
             · {{ focus_recommendation.hero.project.total_hours_spent|round(1) }} hrs invested
        </p>
        <a href="{{ url_for('research_workflow.project_dashboard', project_id=focus_recommendation.hero.project.id) }}" class="position-btn btn-primary-accent" style="margin-top: 0.75rem;">
            <i class="bi bi-arrow-right-circle"></i> Continue Research
        </a>
    </div>

    {% if focus_recommendation.runners_up %}
    <div class="research-focus-runners">
        <p class="research-focus-runners-label">Also active:</p>
        {% for runner in focus_recommendation.runners_up[:4] %}
        <div class="research-focus-runner-row">
            <a href="{{ url_for('research_workflow.project_dashboard', project_id=runner.project.id) }}" class="research-focus-runner-link">
                {{ runner.project.subject_display_name }}
            </a>
            <span class="research-focus-runner-meta">
                {{ runner.project.progress_percentage }}%
                {% if runner.days_idle > 0 %} · {{ runner.days_idle }}d idle{% endif %}
            </span>
            <span class="research-focus-badge research-focus-badge-{{ runner.label|lower|replace(' ', '-') }}">{{ runner.label }}</span>
        </div>
        {% endfor %}
    </div>
    {% endif %}

    {% for warning in focus_recommendation.warnings %}
    <div class="research-focus-warning">
        <i class="bi bi-exclamation-triangle"></i>
        {{ warning.message }}
    </div>
    {% endfor %}
</div>
{% elif active_projects_list %}
{# Fallback: show old-style list if service returned nothing #}
{% for project in active_projects_list[:3] %}
<div class="priority-task">
    <div class="priority-task-checkbox"><i class="bi bi-circle"></i></div>
    <div class="priority-task-content">
        <p class="priority-task-title">
            Continue research on <a href="{{ url_for('research_workflow.project_dashboard', project_id=project.id) }}">{{ project.company.name }}</a>
        </p>
        <p class="priority-task-meta">Step {{ project.current_step_index + 1 }}/{{ project.template.workflow_steps|length }} · {{ project.progress_percentage }}% complete</p>
    </div>
</div>
{% endfor %}
{% else %}
<div class="priority-task">
    <div class="priority-task-checkbox"><i class="bi bi-lightbulb"></i></div>
    <div class="priority-task-content">
        <p class="priority-task-title">No active research projects</p>
        <p class="priority-task-meta">
            {% if inbox_count > 0 %}
                <a href="{{ url_for('ideas.inbox') }}">{{ inbox_count }} idea{{ 's' if inbox_count != 1 }} waiting</a> in your inbox
            {% else %}
                Capture an idea to get started
            {% endif %}
        </p>
    </div>
</div>
{% endif %}
```

**Step 2: Commit**

```bash
git add app/dashboard/templates/dashboard.html
git commit -m "feat: add Research Focus card to dashboard with hero recommendation and warnings"
```

---

## Task 5: Add CSS for Research Focus Card

**Files:**
- Create: `app/static/css/modules/_research-focus.css`
- Modify: `app/static/css/design-system.css` (add import)

**Step 1: Create the CSS module**

Create `app/static/css/modules/_research-focus.css`:

```css
/* =========================================================================
   RESEARCH FOCUS CARD — Dashboard priority recommendation
   ========================================================================= */

.research-focus-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.25rem;
    margin-bottom: 1rem;
}

.research-focus-header {
    margin-bottom: 1rem;
}

.research-focus-label {
    font-size: 0.6875rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--ink-faint);
}

/* Hero recommendation */
.research-focus-hero {
    margin-bottom: 1rem;
}

.research-focus-hero-title {
    font-family: var(--font-display);
    font-size: 1.125rem;
    font-weight: 700;
    color: #111827;
    margin-bottom: 0.25rem;
    letter-spacing: -0.01em;
}

.research-focus-hero-meta {
    font-size: 0.8125rem;
    color: var(--ink-secondary);
    margin-bottom: 0.125rem;
}

.research-focus-hero-detail {
    font-size: 0.75rem;
    color: var(--ink-muted);
    font-family: var(--font-mono);
}

/* Runners-up */
.research-focus-runners {
    border-top: 1px solid var(--border);
    padding-top: 0.75rem;
    margin-top: 0.75rem;
}

.research-focus-runners-label {
    font-size: 0.6875rem;
    font-weight: 600;
    color: var(--ink-faint);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 0.5rem;
}

.research-focus-runner-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.375rem 0;
    font-size: 0.8125rem;
}

.research-focus-runner-link {
    font-weight: 600;
    color: var(--ink);
    text-decoration: none;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex-shrink: 1;
    min-width: 0;
}

.research-focus-runner-link:hover {
    color: var(--accent);
}

.research-focus-runner-meta {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--ink-faint);
    white-space: nowrap;
    flex-shrink: 0;
}

/* Priority badges */
.research-focus-badge {
    display: inline-flex;
    padding: 0.125rem 0.4375rem;
    border-radius: var(--radius-xs);
    font-size: 0.625rem;
    font-weight: 700;
    white-space: nowrap;
    flex-shrink: 0;
}

.research-focus-badge-continue-next {
    background: var(--success-soft);
    color: #065f46;
}

.research-focus-badge-needs-attention {
    background: var(--warning-soft);
    color: #92400e;
}

.research-focus-badge-consider-pausing {
    background: var(--danger-soft);
    color: #991b1b;
}

/* Warnings */
.research-focus-warning {
    display: flex;
    align-items: flex-start;
    gap: 0.375rem;
    margin-top: 0.75rem;
    padding: 0.625rem 0.75rem;
    border-radius: var(--radius-xs);
    background: var(--warning-soft);
    font-size: 0.75rem;
    font-weight: 500;
    color: #92400e;
    line-height: 1.4;
}

.research-focus-warning i {
    flex-shrink: 0;
    margin-top: 0.0625rem;
}
```

**Step 2: Add the import to design-system.css**

In `app/static/css/design-system.css`, find the modules import section and add:

```css
@import 'modules/_research-focus.css';
```

**Step 3: Commit**

```bash
git add app/static/css/modules/_research-focus.css app/static/css/design-system.css
git commit -m "feat: add Research Focus card CSS module"
```

---

## Task 6: Integrate Scoring into My Projects Route

**Files:**
- Modify: `app/research_workflow/project_management_routes.py` (lines 23-47)

**Step 1: Add import**

At the top of the file, add:

```python
from app.services.research_priority import ResearchPriorityService
```

**Step 2: Add priority data to the active_data serialization**

In the `my_projects()` function, after the existing `active_projects` query (line 31), add the scoring call:

```python
# Score and rank active projects
ranked_scores = ResearchPriorityService.rank_projects(current_user)
score_by_project_id = {s.project.id: s for s in ranked_scores}
```

Then in the `active_data.append(...)` dict (lines 35-47), add these keys after `'dashboard_url'`:

```python
'priority_score': round(score_by_project_id[p.id].total, 1) if p.id in score_by_project_id else 0,
'priority_label': score_by_project_id[p.id].label if p.id in score_by_project_id else '',
'days_idle': score_by_project_id[p.id].days_idle if p.id in score_by_project_id else 0,
```

**Step 3: Sort active_data by priority score (default)**

After building `active_data`, add the sort parameter handling:

```python
# Sort by priority score by default
sort_by = request.args.get('sort', 'priority')
if sort_by == 'priority':
    active_data.sort(key=lambda x: x['priority_score'], reverse=True)
elif sort_by == 'last_worked':
    active_data.sort(key=lambda x: x['last_worked'] or '', reverse=True)
elif sort_by == 'progress':
    active_data.sort(key=lambda x: x['progress'], reverse=True)
elif sort_by == 'newest':
    pass  # Already in DB order (created_at desc would need a query change)
```

**Step 4: Pass the project limit and sort to the template**

In the `return render_template(...)` call, add to the `metrics` dict:

```python
'project_limit': ResearchPriorityService.get_focus_recommendation(current_user).project_limit,
```

And add a top-level template variable:

```python
current_sort=sort_by,
```

**Step 5: Commit**

```bash
git add app/research_workflow/project_management_routes.py
git commit -m "feat: add priority scoring to My Projects active research data"
```

---

## Task 7: Add Priority Badges and Sort to My Projects Template

**Files:**
- Modify: `app/research_workflow/templates/projects_dashboard.html`

**Step 1: Add sort dropdown to the Active Research panel controls**

Find the `rcl-panel-controls` div inside the Active Research tab. After the existing status filter `<select>`, add a sort dropdown:

```html
<select id="active-sort" class="rcl-filter-select" onchange="window.location.href='?sort=' + this.value">
    <option value="priority" {{ 'selected' if current_sort == 'priority' }}>Sort: Priority</option>
    <option value="last_worked" {{ 'selected' if current_sort == 'last_worked' }}>Sort: Last Worked</option>
    <option value="progress" {{ 'selected' if current_sort == 'progress' }}>Sort: Progress</option>
    <option value="newest" {{ 'selected' if current_sort == 'newest' }}>Sort: Newest</option>
</select>
```

**Step 2: Add priority columns to the Tabulator JS config**

Find the JavaScript section that initializes the Tabulator table for `#active-research-table`. Add these columns to the column definition:

After the existing `status` column, add:

```javascript
{
    title: "Priority",
    field: "priority_label",
    width: 130,
    formatter: function(cell) {
        var label = cell.getValue();
        if (!label) return '';
        var cls = '';
        if (label === 'Continue next') cls = 'research-focus-badge-continue-next';
        else if (label === 'Needs attention') cls = 'research-focus-badge-needs-attention';
        else cls = 'research-focus-badge-consider-pausing';
        return '<span class="research-focus-badge ' + cls + '">' + label + '</span>';
    },
    headerSort: true,
    sorter: "number",
    sorterParams: { alignEmptyValues: "bottom" },
    accessorDownload: function(value, data) { return data.priority_score; }
},
```

**Step 3: Add over-limit warning to the metrics strip**

In the metrics strip section, after the existing metric items, add a conditional warning:

```html
{% if metrics.active_count > metrics.project_limit %}
<div class="research-focus-warning" style="grid-column: 1 / -1; margin-top: 0.5rem;">
    <i class="bi bi-exclamation-triangle"></i>
    {{ metrics.active_count }} active projects — your focus limit is {{ metrics.project_limit }}.
    Consider pausing or killing {{ metrics.active_count - metrics.project_limit }}.
</div>
{% endif %}
```

**Step 4: Commit**

```bash
git add app/research_workflow/templates/projects_dashboard.html
git commit -m "feat: add priority badges, sort dropdown, and over-limit warning to My Projects"
```

---

## Task 8: Smoke Test & Final Verification

**Step 1: Run the dev server**

```bash
cd /home/warlock20/dev/investment-checklist && venv/bin/python run.py
```

**Step 2: Manual verification checklist**

- [ ] `/dashboard` loads without errors
- [ ] Research Focus card appears if there are active projects
- [ ] Hero project shows company name, current step, progress %, days idle, hours
- [ ] "Continue Research" button links to the correct project dashboard
- [ ] Runners-up show with priority badges
- [ ] Over-limit warning appears if active projects > limit
- [ ] Stale project warning appears for idle projects with low progress
- [ ] Empty state shows "No active research" if no projects exist
- [ ] `/research/workflow/my-projects` loads without errors
- [ ] Default sort is by priority score (highest first)
- [ ] Sort dropdown works: priority, last worked, progress, newest
- [ ] Priority badge column appears in the Tabulator table
- [ ] Over-limit warning appears in metrics strip when applicable

**Step 3: Final commit (if any template tweaks needed)**

```bash
git add -A
git commit -m "fix: polish Research Focus dashboard integration"
```
