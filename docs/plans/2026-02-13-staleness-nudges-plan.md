# Staleness Nudges Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Surface stale research projects on the Company Research page with two-tier escalating nudges — soft "Idle Xd" badge in the table at 14 days, and an action prompt in a new alerts strip at 21 days with "Move to Too Hard" / "I'll work on it" buttons.

**Architecture:** Extends the existing `ResearchPriorityService` scoring with a `staleness_tier` field (0/1/2). A new `dashboard-alerts-strip` component sits below the metrics strip for page-level warnings. The over-limit warning migrates from the metrics strip to this new alerts strip. A lightweight `/touch` AJAX endpoint resets the idle clock.

**Tech Stack:** Flask, SQLAlchemy, Alembic, Jinja2, Tabulator JS, vanilla JavaScript

**Design doc:** `docs/plans/2026-02-13-staleness-nudges-design.md`

---

### Task 1: Add `stale_nudge_days` to ResearchSettings

**Files:**
- Modify: `app/models/research.py:560-564` (add column after `stale_warning_days`)
- Create: migration via `flask db migrate`

**Step 1: Add the column to the model**

In `app/models/research.py`, inside the `ResearchSettings` class, add after line 563 (`stale_warning_days`):

```python
stale_nudge_days = db.Column(db.Integer, default=21)
```

The full tuning knobs section should read:

```python
# Tuning knobs
momentum_half_life_days = db.Column(db.Integer, default=3)
staleness_peak_days = db.Column(db.Integer, default=10)
stale_warning_days = db.Column(db.Integer, default=14)
stale_nudge_days = db.Column(db.Integer, default=21)
stale_warning_min_progress = db.Column(db.Integer, default=30)
```

**Step 2: Generate and run migration**

```bash
cd /home/warlock20/dev/investment-checklist
source venv/bin/activate
flask db migrate -m "add stale_nudge_days to research_settings"
flask db upgrade
```

**Step 3: Verify**

```bash
venv/bin/python -c "from app.models import ResearchSettings; print('stale_nudge_days' in [c.name for c in ResearchSettings.__table__.columns])"
```
Expected: `True`

---

### Task 2: Add staleness tier computation to service + route

**Files:**
- Modify: `app/services/research_priority.py:22-32` (add `staleness_tier` to `ProjectScore`)
- Modify: `app/services/research_priority.py:117-121` (compute tier in `score_project`)
- Modify: `app/research_workflow/project_management_routes.py:38-55` (add `staleness_tier` to `active_data`, build `alerts` list)

**Step 1: Add `staleness_tier` field to `ProjectScore`**

In `app/services/research_priority.py`, add to the `ProjectScore` dataclass (after `is_stale_warning`):

```python
staleness_tier: int = 0  # 0=healthy, 1=getting stale, 2=decision needed
```

**Step 2: Compute staleness tier in `score_project`**

In `app/services/research_priority.py`, replace the `is_stale_warning` block (lines ~117-121) with:

```python
# --- Staleness tier ---
if score.days_idle >= settings.stale_nudge_days and progress_pct < settings.stale_warning_min_progress:
    score.staleness_tier = 2
    score.is_stale_warning = True
elif score.days_idle >= settings.stale_warning_days:
    score.staleness_tier = 1
    score.is_stale_warning = score.days_idle > settings.stale_warning_days and progress_pct < settings.stale_warning_min_progress
else:
    score.staleness_tier = 0
    score.is_stale_warning = False
```

**Step 3: Add `staleness_tier` + `mark_too_hard_url` to `active_data` and build `alerts`**

In `app/research_workflow/project_management_routes.py`, in the `my_projects()` function:

Add to each `active_data.append({...})` dict (after `'days_idle'`):

```python
'staleness_tier': score_by_project_id[p.id].staleness_tier if p.id in score_by_project_id else 0,
'mark_too_hard_url': url_for('research_workflow.mark_too_hard', project_id=p.id),
```

After the sort block (after line ~64), add the alerts list construction:

```python
# --- Build alerts for the header alerts strip ---
settings = ResearchSettings.get_or_create(current_user.id)
alerts = []

# Staleness Tier 2 nudges (sorted by days_idle desc — most urgent first)
tier2_projects = sorted(
    [p for p in active_data if p['staleness_tier'] == 2],
    key=lambda x: x['days_idle'],
    reverse=True,
)
for p in tier2_projects:
    alerts.append({
        'type': 'stale_nudge',
        'project_id': p['id'],
        'company_name': p['company_name'],
        'days_idle': p['days_idle'],
        'progress': p['progress'],
        'mark_too_hard_url': p['mark_too_hard_url'],
        'touch_url': url_for('research_workflow.touch_project', project_id=p['id']),
    })

# Over-limit warning
if active_count > settings.active_project_limit:
    over_by = active_count - settings.active_project_limit
    alerts.append({
        'type': 'over_limit',
        'active_count': active_count,
        'project_limit': settings.active_project_limit,
        'over_by': over_by,
    })
```

Note: `active_count` is already computed further down in the route (line ~128). Move its computation up before the alerts block, or compute it inline:

```python
active_count = len([p for p in active_data if p['status'] == 'active'])
```

Add `alerts` and `alerts_json` to the `render_template` call:

```python
alerts=alerts,
alerts_json=json.dumps(alerts),
```

**Step 4: Verify**

```bash
cd /home/warlock20/dev/investment-checklist
source venv/bin/activate
venv/bin/python -c "
from app import create_app
app = create_app()
with app.app_context():
    from app.services.research_priority import ResearchPriorityService, ProjectScore
    print('staleness_tier' in ProjectScore.__dataclass_fields__)
"
```
Expected: `True`

---

### Task 3: Add `touch_project` AJAX route

**Files:**
- Modify: `app/research_workflow/project_management_routes.py` (add new route after `delete_research_project`)

**Step 1: Add the route**

Add this route at the end of the file (after the `delete_research_project` function):

```python
@research_workflow_bp.route('/projects/<int:project_id>/touch', methods=['POST'])
@login_required
def touch_project(project_id):
    """Reset the idle clock — user acknowledged the staleness nudge."""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return jsonify({'ok': False, 'error': 'Access denied'}), 403

    project.last_worked_at = now_utc()
    db.session.commit()

    return jsonify({'ok': True})
```

Add `jsonify` to the Flask imports at the top of the file:

```python
from flask import render_template, request, redirect, url_for, flash, current_app, jsonify
```

**Step 2: Verify route registration**

```bash
cd /home/warlock20/dev/investment-checklist
source venv/bin/activate
venv/bin/python -c "
from app import create_app
app = create_app()
with app.app_context():
    rules = [r.rule for r in app.url_map.iter_rules() if 'touch' in r.rule]
    print(rules)
"
```
Expected: `['/research/workflow/projects/<int:project_id>/touch']`

---

### Task 4: CSS — `dashboard-alerts-strip` + idle badge tweak

**Files:**
- Modify: `app/static/css/modules/_dashboard.css` (add alerts strip styles after `dashboard-metrics-strip` block)
- Modify: `app/static/css/modules/_research-command-center.css:544-549` (update idle badge for Tier 1)

**Step 1: Add `dashboard-alerts-strip` to `_dashboard.css`**

Add after the `dashboard-metrics-strip` responsive block (after the `@media (max-width: 768px)` block for metrics-strip):

```css
/* Alerts strip — stacked warnings below metrics strip */
.dashboard-alerts-strip {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
    padding-top: var(--space-md);
    border-top: 1px solid var(--border-light);
}

.dashboard-alert-card {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    padding: var(--space-sm) var(--space-md);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-sm);
    line-height: 1.4;
}

.dashboard-alert-card--warning {
    background: var(--warning-soft, var(--warning-50));
    color: #92400e;
}

.dashboard-alert-card--danger {
    background: var(--danger-50);
    color: var(--danger-600);
}

.dashboard-alert-card i {
    flex-shrink: 0;
}

.dashboard-alert-card__text {
    flex: 1;
    min-width: 0;
}

.dashboard-alert-card__actions {
    display: flex;
    gap: var(--space-xs);
    flex-shrink: 0;
}

.dashboard-alert-card__actions .position-btn {
    font-size: var(--font-size-xs);
    padding: 0.2rem 0.6rem;
}

.dashboard-alerts-more {
    font-size: var(--font-size-xs);
    color: var(--text-muted);
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    flex-shrink: 0;
    margin-left: var(--space-sm);
}

.dashboard-alerts-more button {
    background: none;
    border: none;
    color: var(--accent-500);
    font-size: var(--font-size-xs);
    font-weight: 600;
    cursor: pointer;
    padding: 0;
    text-decoration: underline;
}

.dashboard-alerts-expanded {
    display: none;
}

.dashboard-alerts-expanded.is-open {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
}
```

**Step 2: Update idle badge for Tier 1 in `_research-command-center.css`**

The existing `.rcl-cell-badge--idle` (line 544) uses danger colors. Change it to amber/warning for Tier 1 (soft flag):

Replace lines 544-549:

```css
.rcl-cell-badge--idle {
    background: var(--warning-50);
    color: #b45309;
    font-size: var(--font-size-xs);
    padding: 0.1rem 0.35rem;
}
```

---

### Task 5: Template + JS — alerts strip, status formatter, AJAX

**Files:**
- Modify: `app/research_workflow/templates/projects_dashboard.html:25-72` (header card restructure)
- Modify: `app/research_workflow/templates/projects_dashboard.html:334-346` (Status column formatter)
- Modify: `app/research_workflow/templates/projects_dashboard.html` (add AJAX handler in script block)

**Step 1: Restructure the header card**

Replace the `dashboard-metrics-strip` block (lines 25-71) — remove the over-limit warning from inside it and add the new `dashboard-alerts-strip` after it.

The metrics strip should become (lines 25-63, keeping only `portfolio-metric` items):

```html
<div class="dashboard-metrics-strip">
    <div class="portfolio-metric">
        <div class="portfolio-metric-value" style="color: var(--accent-600);">{{ metrics.active_count }}</div>
        <div class="portfolio-metric-label">Active</div>
    </div>
    {% if metrics.paused_count > 0 %}
    <div class="portfolio-metric">
        <div class="portfolio-metric-value" style="color: var(--warning-500);">{{ metrics.paused_count }}</div>
        <div class="portfolio-metric-label">Paused</div>
    </div>
    {% endif %}
    <div class="portfolio-metric">
        <div class="portfolio-metric-value">{{ metrics.watchlist_count }}</div>
        <div class="portfolio-metric-label">Watchlist</div>
    </div>
    <div class="portfolio-metric">
        <div class="portfolio-metric-value" style="color: var(--danger-500);">{{ metrics.too_hard_count }}</div>
        <div class="portfolio-metric-label">Too Hard</div>
    </div>
    <div class="portfolio-metric">
        <div class="portfolio-metric-value" style="color: var(--success-500);">{{ metrics.selectivity_rate }}%</div>
        <div class="portfolio-metric-label">Selectivity</div>
    </div>
    <div class="portfolio-metric">
        <div class="portfolio-metric-value">{{ metrics.total_time }}h</div>
        <div class="portfolio-metric-label">Time Invested</div>
    </div>
    <div class="portfolio-metric">
        <div class="portfolio-metric-value">{{ quick_stats.avg_time }}h</div>
        <div class="portfolio-metric-label">Avg / Company</div>
    </div>
    <div class="portfolio-metric">
        <div class="portfolio-metric-value">{{ quick_stats.invested_count }}</div>
        <div class="portfolio-metric-label">Invested</div>
    </div>
    <div class="portfolio-metric">
        <div class="portfolio-metric-value" style="color: var(--accent-600);">{{ quick_stats.invest_rate }}%</div>
        <div class="portfolio-metric-label">Invest Rate</div>
    </div>
</div>
```

Then add the alerts strip right after the metrics strip, before the closing `</div>` of `dashboard-header-card`:

```html
{% if alerts %}
<div class="dashboard-alerts-strip" id="alerts-strip">
    {# First (most urgent) alert always visible #}
    {% set first = alerts[0] %}
    <div class="dashboard-alert-card dashboard-alert-card--warning" id="alert-{{ first.project_id or 'limit' }}">
        <i class="bi bi-exclamation-triangle"></i>
        <span class="dashboard-alert-card__text">
            {% if first.type == 'stale_nudge' %}
                <strong>{{ first.company_name }}</strong> idle {{ first.days_idle }}d &middot; {{ first.progress }}% done &mdash; Still pursuing?
            {% elif first.type == 'over_limit' %}
                {{ first.active_count }} active projects &mdash; your focus limit is {{ first.project_limit }}. Consider pausing or killing {{ first.over_by }}.
            {% endif %}
        </span>
        {% if first.type == 'stale_nudge' %}
        <div class="dashboard-alert-card__actions">
            <a href="{{ first.mark_too_hard_url }}" class="position-btn" style="font-size: var(--font-size-xs); padding: 0.2rem 0.6rem;">Too Hard</a>
            <button class="position-btn" onclick="touchProject({{ first.project_id }}, '{{ first.touch_url }}')" style="font-size: var(--font-size-xs); padding: 0.2rem 0.6rem;">I'll work on it</button>
        </div>
        {% endif %}
        {% if alerts|length > 1 %}
        <div class="dashboard-alerts-more">
            +{{ alerts|length - 1 }} more
            <button onclick="toggleAlerts()">Show all</button>
        </div>
        {% endif %}
    </div>

    {# Expanded: remaining alerts (hidden by default) #}
    {% if alerts|length > 1 %}
    <div class="dashboard-alerts-expanded" id="alerts-expanded">
        {% for alert in alerts[1:] %}
        <div class="dashboard-alert-card dashboard-alert-card--warning" id="alert-{{ alert.project_id or 'limit' }}">
            <i class="bi bi-exclamation-triangle"></i>
            <span class="dashboard-alert-card__text">
                {% if alert.type == 'stale_nudge' %}
                    <strong>{{ alert.company_name }}</strong> idle {{ alert.days_idle }}d &middot; {{ alert.progress }}% done &mdash; Still pursuing?
                {% elif alert.type == 'over_limit' %}
                    {{ alert.active_count }} active projects &mdash; your focus limit is {{ alert.project_limit }}. Consider pausing or killing {{ alert.over_by }}.
                {% endif %}
            </span>
            {% if alert.type == 'stale_nudge' %}
            <div class="dashboard-alert-card__actions">
                <a href="{{ alert.mark_too_hard_url }}" class="position-btn" style="font-size: var(--font-size-xs); padding: 0.2rem 0.6rem;">Too Hard</a>
                <button class="position-btn" onclick="touchProject({{ alert.project_id }}, '{{ alert.touch_url }}')" style="font-size: var(--font-size-xs); padding: 0.2rem 0.6rem;">I'll work on it</button>
            </div>
            {% endif %}
        </div>
        {% endfor %}
        <button class="dashboard-alerts-more" onclick="toggleAlerts()" style="align-self: flex-start;">Collapse</button>
    </div>
    {% endif %}
</div>
{% endif %}
```

**Step 2: Update the Status column formatter in the Tabulator config**

Replace the Status column formatter (lines ~340-346) to append the Tier 1 idle badge:

```javascript
{
    title: "Status",
    field: "status",
    sorter: "string",
    hozAlign: "center",
    minWidth: 120,
    formatter: function(cell) {
        const row = cell.getRow().getData();
        const val = cell.getValue();
        const modifiers = { 'active': 'active', 'paused': 'paused' };
        const mod = modifiers[val] || 'default';
        let html = `<span class="rcl-cell-badge rcl-cell-badge--${mod}">${val}</span>`;
        if (row.staleness_tier >= 1 && row.days_idle > 0) {
            html += ` <span class="rcl-cell-badge rcl-cell-badge--idle">Idle ${row.days_idle}d</span>`;
        }
        return html;
    }
},
```

Also remove the old inline `Idle` badge from the Company column formatter (lines ~304-308). Replace:

```javascript
const overdue = row.is_overdue ? ' <span class="rcl-cell-badge rcl-cell-badge--idle">Idle</span>' : '';
return `<strong>${cell.getValue()}</strong>${overdue}${ticker}`;
```

With:

```javascript
return `<strong>${cell.getValue()}</strong>${ticker}`;
```

**Step 3: Add the AJAX handler and toggle function in the script block**

Add this inside the `DOMContentLoaded` handler, at the end of the script block:

```javascript
// =========================================================================
// Staleness Nudge Actions
// =========================================================================

window.touchProject = function(projectId, touchUrl) {
    fetch(touchUrl, { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.ok) {
                // Remove the alert card
                const alertEl = document.getElementById('alert-' + projectId);
                if (alertEl) {
                    alertEl.style.transition = 'opacity 0.3s';
                    alertEl.style.opacity = '0';
                    setTimeout(() => alertEl.remove(), 300);
                }

                // Update the table row — reset staleness tier
                if (activeTable) {
                    const row = activeTable.getRows().find(r => r.getData().id === projectId);
                    if (row) {
                        row.update({ staleness_tier: 0, days_idle: 0 });
                    }
                }

                // Update "+N more" count
                const moreEl = document.querySelector('.dashboard-alerts-more');
                if (moreEl) {
                    const remaining = document.querySelectorAll('.dashboard-alert-card').length - 1;
                    if (remaining <= 0) {
                        const strip = document.getElementById('alerts-strip');
                        if (strip) strip.remove();
                    }
                }
            }
        });
};

window.toggleAlerts = function() {
    const expanded = document.getElementById('alerts-expanded');
    if (expanded) {
        expanded.classList.toggle('is-open');
        // Update button text
        const moreBtn = document.querySelector('.dashboard-alerts-more button');
        if (moreBtn) {
            moreBtn.textContent = expanded.classList.contains('is-open') ? 'Collapse' : 'Show all';
        }
    }
};
```

---

### Task 6: Smoke test

**Step 1: Run the app and verify**

```bash
cd /home/warlock20/dev/investment-checklist
source venv/bin/activate
venv/bin/python run.py
```

**Step 2: Check the following on `http://localhost:5000/research/workflow/my-projects`:**

1. Metrics strip has NO warning banner inside it (clean metrics only)
2. If any projects are Tier 2 stale (idle >= 21d, progress < 30%), the `dashboard-alerts-strip` appears below the metrics
3. The most urgent stale project shows with "Too Hard" and "I'll work on it" buttons
4. If there are multiple alerts, "+N more" and "Show all" appear
5. Clicking "Show all" reveals remaining alerts; clicking "Collapse" hides them
6. Clicking "I'll work on it" fades the alert card and removes the idle badge from the table row
7. The Status column shows "active" badge + amber "Idle Xd" badge for Tier 1+ projects
8. Over-limit warning (if applicable) appears in the alerts strip instead of the metrics strip
9. "Too Hard" button navigates to the existing mark_too_hard form

**Step 3: Verify touch endpoint directly**

```bash
# In another terminal, test the touch endpoint (replace PROJECT_ID and session cookie)
curl -X POST http://localhost:5000/research/workflow/projects/1/touch \
  --cookie "session=YOUR_SESSION_COOKIE" \
  -H "Content-Type: application/json"
```

Expected: `{"ok": true}`
