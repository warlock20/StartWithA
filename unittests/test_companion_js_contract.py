# StartWithA
# Copyright (C) 2024-2026 Kiran Mathews
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Static contract checks on companion.js. No app/DB needed.

Covers the seamless-chat behaviours (threads, open state, resume) and the
docked rail surface that replaced the floating bubble.
"""

import os

JS = os.path.join(os.path.dirname(__file__), '..', 'app/static/js/companion.js')
WIDGET = os.path.join(
    os.path.dirname(__file__), '..', 'app/templates/main/_companion_widget.html')
CSS = os.path.join(
    os.path.dirname(__file__), '..', 'app/static/css/modules/_companion.css')
ARGOS_CHECK = os.path.join(
    os.path.dirname(__file__), '..',
    'app/research_workflow/templates/partials/_argos_check.html')


def _js():
    return open(JS, encoding='utf-8').read()


def test_js_posts_to_companion_ask_with_focus_and_history():
    s = _js()
    assert '/ask' in s
    assert 'focus' in s
    assert 'history' in s


def test_js_persists_thread_in_sessionstorage():
    s = _js()
    assert 'sessionStorage' in s


def test_js_has_focus_specific_quick_actions():
    s = _js()
    assert 'What did I miss' in s          # company focus
    assert 'Where am I concentrated' in s  # portfolio focus (factual, not a "risk")
    assert 'Checkpoints due' in s          # portfolio focus
    assert 'Past mistakes' in s            # company focus
    assert 'renderQuickActions' in s


def test_js_threads_are_per_context():
    """Each focus context keeps its own thread (company/portfolio/project/general)."""
    s = _js()
    assert 'focusKey' in s
    assert 'companion.thread:' in s


def test_js_persists_open_state():
    """Rail expanded/collapsed survives navigation (tab-global)."""
    s = _js()
    assert 'companion.open' in s
    assert 'setOpen' in s


def test_js_targets_the_rail_not_the_bubble():
    """The surface is a docked rail; the FAB + slide-up panel are gone."""
    s = _js()
    assert 'companionRail' in s           # config + collapse target
    assert 'companionRailBadge' in s      # unread dot when an answer lands collapsed
    assert "classList.toggle('collapsed'" in s
    assert 'companionFab' not in s        # bubble removed, not hidden
    assert 'companionPanel' not in s


def test_js_resumes_pending_task_per_context():
    """A still-running answer is re-attached after navigation, per context."""
    s = _js()
    assert 'companion.pending:' in s
    assert 'resumePending' in s
    assert 'startedAt' in s


def test_js_sends_current_page_context():
    """The companion tells the agent which page the user is on (URL + title)."""
    s = _js()
    assert 'window.location.pathname' in s
    assert 'document.title' in s


def test_js_shows_scope_indicator():
    """Header names the current scope so a shared 'general' thread isn't confusing."""
    s = _js()
    assert 'scopeLabel' in s
    assert 'companionScope' in s
    assert 'Across your whole account' in s   # general
    assert 'Focused on this company' in s     # company


def test_js_renders_markdown_answers():
    """Answers are markdown from the agent; render via marked + DOMPurify (sanitized)."""
    s = _js()
    assert 'renderMarkdown' in s
    assert 'marked.parse' in s        # markdown -> HTML
    assert 'DOMPurify.sanitize' in s  # sanitize LLM output before innerHTML
    # No longer rendered as plain escaped text:
    assert 'this.escapeHtml(answer)' not in s


def test_js_surfaces_insights_from_the_warnings_endpoint():
    """Task 3: the rail shows the user's own history, at zero token cost."""
    s = _js()
    assert 'loadInsights' in s
    assert '/warnings?company_id=' in s      # existing zero-token endpoint
    assert 'companionInsights' in s
    assert 'Surfaced for you' in s


def test_js_only_surfaces_insights_when_a_company_is_in_focus():
    """Warnings are per-company; an unfocused page has nothing to surface.

    The section is left absent rather than empty-stated — an account-wide
    'surfaced' feed is a different feature.
    """
    s = _js()
    loader = s[s.index('loadInsights'):]
    guard = loader[:loader.index('\n    },')]
    assert 'company_id' in guard, 'insights must be gated on a company focus'


def test_js_binds_the_expand_shortcut():
    """The rail expands from the keyboard without reaching for the tab."""
    s = _js()
    assert 'metaKey' in s and 'ctrlKey' in s
    assert "'.'" in s                 # the bound key, however the guard is written
    assert 'keydown' in s


def test_js_drives_the_collapsed_status_lights():
    """Orb pulses while a question is running; lights show what's waiting."""
    s = _js()
    assert 'setRunning' in s
    assert 'companionStatusRunning' in s
    assert 'companionStatusInsights' in s


def test_widget_has_the_collapsed_status_rail():
    """The 44px strip carries the orb, unread badge and status lights.

    Three lights only. There is deliberately no 'needs review' light: the Dashboard
    already surfaces upcoming reviews, and the only data behind one here would be
    Destination Analysis checkpoints under a label promising more than that.
    """
    html = open(WIDGET, encoding='utf-8').read()
    assert 'id="companionRailOrb"' in html
    assert 'id="companionRailBadge"' in html
    assert 'id="companionStatusRunning"' in html
    assert 'id="companionStatusInsights"' in html
    assert 'companionStatusReview' not in html


def test_widget_has_scope_element():
    html = open(WIDGET, encoding='utf-8').read()
    assert 'companionScope' in html


def test_widget_has_an_insights_mount():
    html = open(WIDGET, encoding='utf-8').read()
    assert 'id="companionInsights"' in html


def test_widget_renders_a_rail():
    """The markup is a docked rail with an edge tab, not a floating bubble."""
    html = open(WIDGET, encoding='utf-8').read()
    assert 'companion-rail' in html
    assert 'id="companionRail"' in html
    assert 'id="companionRailTab"' in html
    assert 'companion-fab' not in html
    assert 'companion-panel' not in html


def test_rail_css_replaced_the_bubble_css():
    """The FAB/panel rules are deleted, and the rail is styled in their place."""
    css = open(CSS, encoding='utf-8').read()
    assert '.companion-rail' in css
    assert '.companion-fab' not in css
    assert '.companion-panel' not in css


def test_only_the_argos_modal_still_uses_the_alert_item_rules():
    """The alert-item family predates the rail and is NOT a separate feature —
    it rendered the same warnings the rail now shows.

    The sidebar card (.companion-alerts-*) and the never-used banner
    (.companion-banner-*) are gone; the item rules stay because the Argos modal's
    Research Intelligence tab still renders them.
    """
    css = open(CSS, encoding='utf-8').read()
    assert '.companion-alert-item' in css
    assert '#argosModal .companion-alert-item' in css
    assert '.companion-alerts-card' not in css
    assert '.companion-banner' not in css

    argos = open(ARGOS_CHECK, encoding='utf-8').read()
    assert 'companion-alert-item' in argos


def test_widget_exposes_focus_dataset():
    html = open(WIDGET, encoding='utf-8').read()
    assert 'data-focus-type' in html
    assert 'data-focus-company-id' in html
    assert 'data-focus-project-id' in html
    assert 'data-endpoint-base="/companion"' in html


if __name__ == '__main__':
    test_js_posts_to_companion_ask_with_focus_and_history()
    test_js_persists_thread_in_sessionstorage()
    test_widget_exposes_focus_dataset()
    print("PASS")
