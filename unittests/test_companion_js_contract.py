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

"""Static contract checks on companion.js (Task 14). No app/DB needed."""

import os

JS = os.path.join(os.path.dirname(__file__), '..', 'app/static/js/companion.js')
WIDGET = os.path.join(
    os.path.dirname(__file__), '..', 'app/templates/main/_companion_widget.html')


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
    """Panel open/closed survives navigation (tab-global)."""
    s = _js()
    assert 'companion.open' in s
    assert 'setOpen' in s


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


def test_widget_has_scope_element():
    html = open(WIDGET, encoding='utf-8').read()
    assert 'companionScope' in html


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
