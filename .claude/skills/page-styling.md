---
name: page-styling
description: Use when creating or modifying HTML templates. Defines the two standard page patterns and CSS conventions used across the platform.
---

# Page Styling Conventions

This skill defines the two standard page layout patterns used across the platform. **Every new page must follow one of these two patterns.** No custom one-off patterns (e.g., `checkpoint-edit-container`, `quick-capture-card`) are allowed.

---

## Pattern 1: Dashboard Pages

**When to use**: List pages, dashboards, detail views, and any information-dense page with multiple sections of content.

**CSS source**: `app/static/css/modules/_dashboard.css`

**Used by ~51 templates** including: inbox, portfolio_dashboard, question_bank, sector_analysis, position_detail, etc.

### Structure

```html
{% extends "main/_base.html" %}

{% block content %}
<div class="dashboard-container">
    <!-- Header (REQUIRED on every page) -->
    <div class="dashboard-header-card">
        <header class="dashboard-header">
            <div>
                <h1 class="dashboard-title font-poppins">Page Title</h1>
                <p class="dashboard-subtitle">Brief description</p>
            </div>
            <div class="dashboard-header-actions">
                {% with btn_class='btn btn-outline-secondary' %}
                    {% include 'components/smart_back_button.html' %}
                {% endwith %}
            </div>
        </header>

        <!-- Optional: Metrics strip (inside header-card) -->
        <div class="dashboard-metrics-strip">
            <div class="portfolio-metric">
                <div class="portfolio-metric-icon"><i class="bi bi-graph-up"></i></div>
                <span class="portfolio-metric-label">Label</span>
                <span class="portfolio-metric-value">Value</span>
            </div>
        </div>

        <!-- Optional: Alerts strip (inside header-card, after metrics) -->
        <div class="dashboard-alerts-strip">
            <div class="dashboard-alert-card dashboard-alert-card--warning">
                Alert content
            </div>
        </div>
    </div>

    <!-- Page body content goes here (Bootstrap grid, cards, tables, etc.) -->
</div>
{% endblock %}
```

### Per-Company Pages

For pages tied to a specific company, wrap the title in identity classes:

```html
<div class="dashboard-header-identity">
    <div class="dashboard-header-logo">
        <i class="bi bi-building"></i>
    </div>
    <h1 class="dashboard-title font-poppins">Company Name</h1>
</div>
```

---

## Pattern 2: Focused Action Pages

**When to use**: Any page where the user completes a **single focused task** and moves on — creating something new, editing an entity, running an evaluation, promoting/transitioning, recording a review. The key trait is a **centered form with step-by-step sections**.

**CSS sources**: `app/static/css/modules/_action-page.css` (layout) + `app/static/css/modules/_idea-capture.css` (form elements)

**Used by ~9 templates**: add_idea, add_transaction, new_entry, kill_room, promote_idea, new_mistake, weekly_review, add_thesis_version, edit_question.

**Examples of action pages that modify existing data** (not just "create new"):
- `kill_room.html` — evaluating and potentially killing an existing idea
- `promote_idea.html` — transitioning an existing idea to a research project
- `edit_question.html` — editing a question bank entry

### Structure

```html
{% extends "main/_base.html" %}

{% block content %}
<div class="action-page">
    <div class="container">
        <!-- Hero Section -->
        <div class="capture-hero">
            <div class="capture-hero-badge">
                <i class="bi bi-plus-circle-fill"></i>
                <span>New Something</span>
            </div>
            <h1>Action Title</h1>
            <p class="capture-hero-subtitle">Brief description of what this does</p>
        </div>

        <!-- Main Form -->
        <div class="capture-form-container">
            <form method="POST" action="...">
                <div class="capture-card">
                    <div class="capture-card-body">
                        <!-- Numbered Sections -->
                        <div class="capture-section">
                            <div class="capture-section-header">
                                <span class="capture-section-number">1</span>
                                <span class="capture-section-title">Section Title</span>
                            </div>

                            <div class="capture-input-group">
                                <label class="capture-label" for="field">
                                    Label<span class="required">*</span>
                                </label>
                                <input type="text" class="capture-input" ...>
                                <p class="capture-input-help">Helper text</p>
                            </div>
                        </div>

                        <div class="capture-divider"></div>

                        <!-- More sections... -->
                    </div>

                    <!-- Submit Section -->
                    <div class="capture-submit-section">
                        <div class="capture-submit-row">
                            <button type="submit" class="capture-submit-btn btn-primary-submit">
                                <i class="bi bi-check-circle-fill"></i>
                                <span>Submit</span>
                            </button>
                            <a href="..." class="capture-cancel-link">Cancel</a>
                        </div>
                    </div>
                </div>
            </form>
        </div>
    </div>
</div>
{% endblock %}
```

### Key Classes

| Element | Class | CSS File |
|---------|-------|----------|
| Page wrapper | `action-page` | `_action-page.css` |
| Hero section | `capture-hero`, `capture-hero-badge`, `capture-hero-subtitle` | `_idea-capture.css` |
| Form container | `capture-form-container` | `_idea-capture.css` |
| Card wrapper | `capture-card`, `capture-card-body` | `_idea-capture.css` |
| Sections | `capture-section`, `capture-section-header`, `capture-section-number`, `capture-section-title` | `_idea-capture.css` |
| Inputs | `capture-input-group`, `capture-label`, `capture-input`, `capture-input-lg`, `capture-select`, `capture-textarea` | `_idea-capture.css` |
| Rows | `capture-row` (side-by-side inputs) | `_idea-capture.css` |
| Divider | `capture-divider` | `_idea-capture.css` |
| Submit | `capture-submit-section`, `capture-submit-btn btn-primary-submit` | `_idea-capture.css` |
| Help text | `capture-input-help` | `_idea-capture.css` |
| Cancel link | `capture-cancel-link` | `_idea-capture.css` |

### Custom Accent Colors

Action pages can override accent colors for different moods:

```html
<!-- Danger/warning actions (kill_room, new_mistake) -->
<div class="action-page" style="--action-accent-from: #dc2626; --action-accent-to: #ef4444;">
```

### Optional Labels

For optional fields, use inline style instead of a separate class:

```html
<label class="capture-label" for="field">
    Field Name <span style="color: var(--gray-400); font-weight: 400;">(optional)</span>
</label>
```

---

## How to Choose Between Pattern 1 and Pattern 2

| Question | Pattern 1 (Dashboard) | Pattern 2 (Action) |
|----------|----------------------|---------------------|
| Is it a list or dashboard? | Yes | No |
| Is it information-dense with multiple content sections? | Yes | No |
| Is it a focused form (create, edit, evaluate)? | No | Yes |
| Does it have numbered step-by-step sections? | No | Yes |
| Does it have a hero section? | No | Yes |
| Does the user do one thing and leave? | No | Yes |

**When in doubt**: If the page is about **viewing/browsing data** with multiple panels, use Pattern 1. If the page is about **completing a focused form** (create, edit, evaluate, promote, record), use Pattern 2.

---

## Common CSS Classes Reference

### Dashboard Layout & Cards (Pattern 1)

| Class | Usage |
|-------|-------|
| `dashboard-container` | Top-level wrapper for all dashboard pages |
| `dashboard-header-card` | Wraps the header section (REQUIRED on all dashboard pages) |
| `dashboard-header` | Flex header with title left, actions right |
| `dashboard-title` | Page title (always paired with `font-poppins`) |
| `dashboard-subtitle` | Description under title |
| `dashboard-header-actions` | Right-aligned action buttons |
| `dashboard-metrics-strip` | Horizontal metrics bar (inside header-card) |
| `dashboard-alerts-strip` | Alert bar (inside header-card, after metrics) |
| `priority-lane-grid` | Card grid layout (use `four-column` modifier for 4-col) |
| `priority-card` | Individual card in a grid |

### Buttons

| Class | Usage |
|-------|-------|
| `position-btn` | Standard action button across the platform |
| `btn btn-outline-secondary` | Back/cancel buttons |
| `capture-submit-btn btn-primary-submit` | Submit button in action forms |

### Metrics

| Class | Usage |
|-------|-------|
| `portfolio-metric` | Metric item container |
| `portfolio-metric-icon` | Icon wrapper |
| `portfolio-metric-label` | Metric label text |
| `portfolio-metric-value` | Metric value text |

### Form Elements (Dashboard Pattern)

Dashboard pages use standard Bootstrap form classes for body content: `form-control`, `form-control-lg`, `form-select`, `form-label`, `mb-3`/`mb-4`.

### Form Elements (Action Pattern)

Action pages use `capture-*` classes (NOT Bootstrap form classes): `capture-input`, `capture-input-lg`, `capture-select`, `capture-textarea`, `capture-label`, `capture-input-group`, `capture-input-help`.

---

## Anti-patterns (DO NOT USE)

These classes have no CSS definitions or are legacy patterns. **Never use them in new templates:**

| Bad Pattern | Why | Correct Alternative |
|-------------|-----|-------------------|
| `quick-capture-card` | No CSS exists for this class | Use `capture-card` (Pattern 2) |
| `quick-capture-submit` | No CSS exists for this class | Use `capture-submit-btn btn-primary-submit` |
| `card-icon`, `card-subtitle` | No CSS exists for these classes | Use `capture-hero-badge` or remove |
| `checkpoint-edit-container` | Legacy non-standard pattern | Use Pattern 2 (action-page) |
| `checkpoint-form-field` | Legacy non-standard pattern | Use `capture-input-group` + `capture-label` + `capture-input` |
| `checkpoint-btn` | Legacy non-standard pattern | Use `capture-submit-btn` or Bootstrap `btn` |
| Custom grid names (e.g., `hub-intel-grid`) | Non-standard | Use `priority-lane-grid` |
| `btn-portfolio-modern` (in headers) | Legacy | Use `position-btn` (ok in body empty states) |

---

## CSS File Locations

All CSS is bundled globally via `app/assets.py` — every page loads every module.

| File | Contains |
|------|----------|
| `app/static/css/modules/_dashboard.css` | `dashboard-header-card`, `dashboard-metrics-strip`, `dashboard-alerts-strip`, `dashboard-container` |
| `app/static/css/modules/_action-page.css` | `action-page`, `action-card`, `action-hero`, `action-footer` |
| `app/static/css/modules/_idea-capture.css` | `capture-hero`, `capture-card`, `capture-input`, `capture-section`, `capture-submit-*`, all `capture-*` form classes |
| `app/static/css/modules/_cards.css` | `priority-card`, `priority-lane-grid` |
| `app/static/css/modules/_checkpoint-edit.css` | Legacy `checkpoint-*` classes (do not use for new pages) |

---

## Decision Checklist for New Pages

When creating a new page, answer these:

1. **Is this a focused form (create, edit, evaluate, record)?** → Use Pattern 2 (action-page + capture-* classes)
2. **Is this a list, dashboard, or detail view?** → Use Pattern 1 (dashboard-container)
3. **Does the page have a header?** → Yes, always. Use `dashboard-header-card` (Pattern 1) or `capture-hero` (Pattern 2)
4. **Does the header show metrics?** → Add `dashboard-metrics-strip` inside `dashboard-header-card`
5. **Does it show a grid of cards?** → Use `priority-lane-grid`
6. **Is it tied to a specific company?** → Add `dashboard-header-identity` + `dashboard-header-logo`
7. **Does the form need side-by-side fields?** → Use `capture-row` (Pattern 2)
