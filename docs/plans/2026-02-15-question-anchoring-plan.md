# Focus Mode Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Focus Mode to the Free Research module — click a question to isolate it, navigate between questions linearly, exit back to full list.

**Architecture:** Pure frontend change. Add Focus Mode CSS classes to `_free-research.css`, add a sticky toolbar HTML element to the template, add a Focus button to each card header, and add focus state management + keyboard shortcuts to the `FreeResearch` JS object.

**Tech Stack:** CSS (design system variables), vanilla JS (existing `FreeResearch` object), Bootstrap Icons, Jinja2 template.

**Design doc:** `docs/plans/2026-02-15-question-anchoring-design.md`
**Prototype:** `docs/design_proposal_question_anchoring.html`

---

### Task 1: Add Focus Mode CSS

**Files:**
- Modify: `app/static/css/modules/_free-research.css` (append after line 401)

**Step 1: Append Focus Mode styles to `_free-research.css`**

Add the following CSS block at the end of the file, after the `.fr-saving-indicator.visible` rule:

```css
/* =============================================================================
   FOCUS MODE
   Isolates a single question for distraction-free research
   ============================================================================= */

/* Focus button in card header */
.fr-focus-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 0.2rem 0.65rem;
    border-radius: var(--radius-pill);
    border: 1px solid var(--border-light);
    background: var(--background-white);
    color: var(--text-muted);
    cursor: pointer;
    font-size: var(--font-size-xs);
    font-weight: 500;
    transition: all var(--transition-fast);
    flex-shrink: 0;
    white-space: nowrap;
}

.fr-focus-btn:hover {
    background: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
    box-shadow: 0 2px 8px rgba(45, 106, 79, 0.25);
}

.fr-focus-btn i {
    font-size: 0.7rem;
}

/* Body state when focus mode is active */
body.focus-mode-active {
    background: #f0f1f5;
}

body.focus-mode-active .free-research-add-section {
    display: none;
}

body.focus-mode-active .fr-complete-section {
    display: none;
}

/* Hidden cards (all except focused) */
.fr-question-card.fr-hidden {
    opacity: 0;
    max-height: 0;
    margin-bottom: 0;
    padding: 0;
    border: none;
    overflow: hidden;
    pointer-events: none;
    transition: opacity 0.25s ease, max-height 0.35s ease 0.05s, margin-bottom 0.35s ease 0.05s;
}

/* Focused card emphasis */
.fr-question-card.fr-focused {
    border-left-color: var(--accent-color);
    border-left-width: 5px;
    box-shadow: var(--shadow-medium), 0 0 0 1px rgba(45, 106, 79, 0.08);
    animation: frFocusSlideIn 0.3s ease;
}

.fr-question-card.fr-focused .fr-question-card-header {
    background: linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%);
}

.fr-question-card.fr-focused .fr-question-expand-icon {
    display: none;
}

.fr-question-card.fr-focused .fr-focus-btn {
    display: none;
}

@keyframes frFocusSlideIn {
    from { opacity: 0; transform: translateY(-8px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* Focus Toolbar (sticky bar at top of main content) */
.fr-focus-toolbar {
    display: none;
    position: sticky;
    top: 0;
    z-index: 50;
    margin-bottom: var(--space-md);
}

.fr-focus-toolbar.visible {
    display: block;
}

.fr-focus-toolbar-inner {
    background: var(--primary-800);
    color: white;
    padding: 0.6rem var(--space-lg);
    border-radius: var(--radius-lg);
    display: flex;
    align-items: center;
    gap: var(--space-md);
    box-shadow: var(--shadow-heavy);
    animation: frFocusSlideIn 0.25s ease;
}

.fr-focus-toolbar-icon {
    width: 28px;
    height: 28px;
    border-radius: var(--radius-sm);
    background: rgba(45, 106, 79, 0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: var(--font-size-sm);
    flex-shrink: 0;
}

.fr-focus-toolbar-label {
    font-size: var(--font-size-xs);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    opacity: 0.6;
    white-space: nowrap;
}

.fr-focus-toolbar-question {
    flex: 1;
    font-size: var(--font-size-sm);
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.fr-focus-toolbar-exit {
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: white;
    padding: 0.3rem 0.75rem;
    border-radius: var(--radius-md);
    cursor: pointer;
    font-size: var(--font-size-xs);
    font-weight: 500;
    white-space: nowrap;
    transition: background var(--transition-fast);
    flex-shrink: 0;
}

.fr-focus-toolbar-exit:hover {
    background: rgba(255, 255, 255, 0.2);
}

.fr-focus-toolbar-kbd {
    font-size: 0.65rem;
    opacity: 0.5;
    margin-left: var(--space-xs);
    border: 1px solid rgba(255, 255, 255, 0.2);
    padding: 1px 4px;
    border-radius: 3px;
    font-family: monospace;
}

/* Focus Navigation (bottom of focused card) */
.fr-focus-nav {
    display: none;
    align-items: center;
    justify-content: space-between;
    margin-top: var(--space-md);
    padding-top: var(--space-md);
    border-top: 1px solid var(--border-light);
}

.fr-question-card.fr-focused .fr-focus-nav {
    display: flex;
}

.fr-focus-nav-btn {
    display: inline-flex;
    align-items: center;
    gap: var(--space-sm);
    padding: var(--space-sm) var(--space-md);
    border-radius: var(--radius-md);
    border: 1px solid var(--border-medium);
    background: var(--background-white);
    color: var(--text-secondary);
    cursor: pointer;
    font-size: var(--font-size-sm);
    font-weight: 500;
    transition: all var(--transition-fast);
}

.fr-focus-nav-btn:hover:not(:disabled) {
    background: var(--gray-100);
    border-color: var(--accent-color);
    color: var(--accent-color);
}

.fr-focus-nav-btn:disabled {
    opacity: 0.35;
    cursor: not-allowed;
}

.fr-focus-nav-center {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
}

.fr-focus-nav-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--gray-300);
    transition: all var(--transition-fast);
}

.fr-focus-nav-dot.current {
    background: var(--accent-color);
    transform: scale(1.3);
}

.fr-focus-nav-dot.answered {
    background: var(--success-500);
}
```

**Step 2: Verify CSS loads**

Run: `venv/bin/python -c "print('CSS file updated — verify in browser')"` (no build step needed, CSS is loaded directly)

**Step 3: Commit**

```bash
git add app/static/css/modules/_free-research.css
git commit -m "feat: add Focus Mode CSS for free research questions"
```

---

### Task 2: Add Focus Toolbar HTML to template

**Files:**
- Modify: `app/research_workflow/templates/free_research_step.html` (lines 30-31, inside `col-lg-8`, before the warning banner)

**Step 1: Add the focus toolbar element**

Insert the following HTML inside `<div class="col-lg-8">`, right before the `<!-- Warning Banner -->` comment (between lines 31 and 32):

```html
            <!-- Focus Mode Toolbar (hidden by default, shown when a question is focused) -->
            <div class="fr-focus-toolbar" id="focusToolbar">
                <div class="fr-focus-toolbar-inner">
                    <div class="fr-focus-toolbar-icon"><i class="bi bi-crosshair"></i></div>
                    <span class="fr-focus-toolbar-label">Focused on:</span>
                    <span class="fr-focus-toolbar-question" id="focusToolbarText"></span>
                    <button class="fr-focus-toolbar-exit" onclick="FreeResearch.exitFocus()">
                        Exit Focus <span class="fr-focus-toolbar-kbd">Esc</span>
                    </button>
                </div>
            </div>
```

**Step 2: Commit**

```bash
git add app/research_workflow/templates/free_research_step.html
git commit -m "feat: add Focus Mode toolbar HTML to free research template"
```

---

### Task 3: Add Focus button and Focus Nav to `renderQuestionCard`

**Files:**
- Modify: `app/research_workflow/templates/free_research_step.html` (lines 382-435, the `renderQuestionCard` method)

**Step 1: Add the Focus button to the card header**

In the `renderQuestionCard` method, insert the Focus button between the status badge and the expand icon (between lines 390-391):

```html
                    <button class="fr-focus-btn" onclick="event.stopPropagation(); FreeResearch.enterFocus(${question.id})" title="Focus on this question">
                        <i class="bi bi-crosshair"></i> Focus
                    </button>
```

**Step 2: Add the Focus Nav to the card body**

Inside the card body, after the `.fr-question-actions` div (after line 432, before the closing `</div>` of the card body), add:

```html
                    <!-- Focus Navigation -->
                    <div class="fr-focus-nav">
                        <button class="fr-focus-nav-btn" onclick="FreeResearch.focusPrev()" id="focusPrev-${question.id}">
                            <i class="bi bi-arrow-left"></i> Previous
                        </button>
                        <div class="fr-focus-nav-center" id="focusDots-${question.id}"></div>
                        <button class="fr-focus-nav-btn" onclick="FreeResearch.focusNext()" id="focusNext-${question.id}">
                            Next <i class="bi bi-arrow-right"></i>
                        </button>
                    </div>
```

**Step 3: Commit**

```bash
git add app/research_workflow/templates/free_research_step.html
git commit -m "feat: add Focus button and nav to question cards"
```

---

### Task 4: Add Focus Mode JS logic to `FreeResearch` object

**Files:**
- Modify: `app/research_workflow/templates/free_research_step.html` (the `FreeResearch` object)

**Step 1: Add `focusedQuestionId` state property**

Add to the properties section (after line 177, after `editors: {}`):

```javascript
    focusedQuestionId: null,  // null = normal mode, question ID = focus mode
```

**Step 2: Add `initKeyboard()` call to `init()`**

In the `init()` method (line 186-189), add `this.initKeyboard();` after `this.initSortable();`.

**Step 3: Add `initKeyboard()` method**

Add in the Initialization section (after `initSortable` method, after line 201):

```javascript
    initKeyboard() {
        document.addEventListener('keydown', (e) => {
            if (this.focusedQuestionId === null) return;
            // Don't capture keys if user is typing in an editor or input
            const tag = e.target.tagName;
            if (tag === 'INPUT' || tag === 'TEXTAREA' || e.target.isContentEditable) return;

            if (e.key === 'Escape') {
                e.preventDefault();
                this.exitFocus();
            } else if (e.key === 'ArrowLeft') {
                e.preventDefault();
                this.focusPrev();
            } else if (e.key === 'ArrowRight') {
                e.preventDefault();
                this.focusNext();
            }
        });
    },
```

**Step 4: Modify `toggleQuestion()` to respect focus mode**

Replace the existing `toggleQuestion` method (lines 438-454) with:

```javascript
    toggleQuestion(questionId) {
        // In focus mode, clicking the header does nothing (card is always expanded)
        if (this.focusedQuestionId !== null) return;

        const card = document.querySelector(`[data-question-id="${questionId}"]`);
        if (!card) return;

        const wasExpanded = card.classList.contains('expanded');

        // Collapse all others
        document.querySelectorAll('.fr-question-card.expanded').forEach(c => {
            c.classList.remove('expanded');
        });

        // Toggle this one
        if (!wasExpanded) {
            card.classList.add('expanded');
            this.initEditorForQuestion(questionId);
        }
    },
```

**Step 5: Add Focus Mode methods**

Add a new section in the JS object (before the `// Utilities` section comment, around line 845):

```javascript
    // =============================================================================
    // Focus Mode
    // =============================================================================

    enterFocus(questionId) {
        this.focusedQuestionId = questionId;
        document.body.classList.add('focus-mode-active');

        // Update toolbar
        const question = this.questions.find(q => q.id === questionId);
        if (question) {
            document.getElementById('focusToolbarText').textContent = question.question_text;
        }
        document.getElementById('focusToolbar').classList.add('visible');

        // Apply classes to cards
        document.querySelectorAll('.fr-question-card').forEach(card => {
            const cardId = parseInt(card.dataset.questionId);
            card.classList.remove('expanded', 'fr-focused', 'fr-hidden');

            if (cardId === questionId) {
                card.classList.add('expanded', 'fr-focused');
                this.initEditorForQuestion(questionId);
            } else {
                card.classList.add('fr-hidden');
            }
        });

        // Update focus nav dots and prev/next buttons
        this.updateFocusNav(questionId);

        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
    },

    exitFocus() {
        if (this.focusedQuestionId === null) return;

        this.focusedQuestionId = null;
        document.body.classList.remove('focus-mode-active');
        document.getElementById('focusToolbar').classList.remove('visible');

        // Remove focus classes from all cards
        document.querySelectorAll('.fr-question-card').forEach(card => {
            card.classList.remove('fr-focused', 'fr-hidden');
        });
    },

    focusPrev() {
        if (this.focusedQuestionId === null) return;
        const currentIndex = this.questions.findIndex(q => q.id === this.focusedQuestionId);
        if (currentIndex > 0) {
            this.enterFocus(this.questions[currentIndex - 1].id);
        }
    },

    focusNext() {
        if (this.focusedQuestionId === null) return;
        const currentIndex = this.questions.findIndex(q => q.id === this.focusedQuestionId);
        if (currentIndex < this.questions.length - 1) {
            this.enterFocus(this.questions[currentIndex + 1].id);
        }
    },

    updateFocusNav(questionId) {
        const currentIndex = this.questions.findIndex(q => q.id === questionId);

        // Update dots
        const dotsContainer = document.getElementById(`focusDots-${questionId}`);
        if (dotsContainer) {
            dotsContainer.innerHTML = this.questions.map((q, i) => {
                let cls = 'fr-focus-nav-dot';
                if (i === currentIndex) cls += ' current';
                else if (q.status === 'answered') cls += ' answered';
                return `<div class="${cls}"></div>`;
            }).join('');
        }

        // Update prev/next disabled state
        const prevBtn = document.getElementById(`focusPrev-${questionId}`);
        const nextBtn = document.getElementById(`focusNext-${questionId}`);
        if (prevBtn) prevBtn.disabled = (currentIndex === 0);
        if (nextBtn) nextBtn.disabled = (currentIndex === this.questions.length - 1);
    },
```

**Step 6: Verify in browser**

Run: `venv/bin/python run.py` and navigate to a free research step. Test:
1. Click "Focus" on a question — card isolates, toolbar appears, others hide
2. Press `ArrowRight`/`ArrowLeft` — navigates between questions
3. Press `Esc` — exits focus mode, all cards reappear
4. Click "Focus", use Prev/Next buttons — works correctly
5. Dot indicators show correct position and answered status

**Step 7: Commit**

```bash
git add app/research_workflow/templates/free_research_step.html
git commit -m "feat: implement Focus Mode JS logic with keyboard navigation"
```

---

### Task 5: Handle edge cases

**Files:**
- Modify: `app/research_workflow/templates/free_research_step.html`

**Step 1: Exit focus on question delete**

In the existing `deleteQuestion` method (lines 289-313), add an exit-focus check. After `if (!confirm(...)) return;` and before the fetch call, add:

```javascript
        // Exit focus mode if deleting the focused question
        if (this.focusedQuestionId === questionId) {
            this.exitFocus();
        }
```

**Step 2: Re-render focus state after add/delete**

In the existing `renderQuestions` method (lines 345-375), add at the end (before the closing `}`), after the tooltip initialization:

```javascript
        // Re-apply focus mode if active
        if (this.focusedQuestionId !== null) {
            // Check if focused question still exists
            const stillExists = this.questions.find(q => q.id === this.focusedQuestionId);
            if (stillExists) {
                this.enterFocus(this.focusedQuestionId);
            } else {
                this.exitFocus();
            }
        }
```

**Step 3: Verify edge cases in browser**

Test:
1. Focus on a question, then delete it — exits focus mode cleanly
2. Focus on a question, add a new question (not possible since add section is hidden — correct behavior)
3. Focus on first question, press ArrowLeft — Prev button disabled, nothing happens
4. Focus on last question, press ArrowRight — Next button disabled, nothing happens

**Step 4: Commit**

```bash
git add app/research_workflow/templates/free_research_step.html
git commit -m "fix: handle edge cases in Focus Mode (delete, re-render)"
```

---

### Task 6: Final smoke test and commit position-btn change

**Files:**
- Already modified: `app/static/css/modules/_position-detail.css`

**Step 1: Verify position-btn radius change**

The `position-btn` border-radius was already changed from `--radius-sm` to `--radius-md` in `_position-detail.css`. Visually verify that buttons across the platform (portfolio dashboard, position detail, etc.) now show the slightly rounder 8px corners.

**Step 2: Full commit of all changes**

```bash
git add app/static/css/modules/_position-detail.css
git commit -m "style: update position-btn border-radius to 8px"
```

**Step 3: Final verification**

Run through the full flow:
1. Navigate to a Free Research step
2. Add 2-3 questions if none exist
3. Click Focus on question 2 — toolbar shows, others hide, card expands
4. Arrow keys navigate between questions
5. Esc exits cleanly
6. Status badges and dot indicators reflect correct states
7. All existing functionality (expand/collapse, AI tools, status toggle, drag reorder) still works in normal mode
