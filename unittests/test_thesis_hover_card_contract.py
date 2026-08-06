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

"""Static contract checks on the thesis hover card. No app or DB needed.

Guards the properties that are easy to regress silently: escaping, event
delegation (Tabulator virtualises rows), the mouse-only hover gate, and the
body mount that keeps the card out of the cell's overflow:hidden.
"""

import os
import re

JS = os.path.join(
    os.path.dirname(__file__), '..', 'app/static/js/thesis-hover-card.js')


def _js():
    return open(JS, encoding='utf-8').read()


def test_exposes_the_init_entry_point():
    assert 'window.initThesisHoverCard' in _js()


def test_user_text_is_escaped_before_insertion():
    s = _js()
    assert 'function escapeHtml(' in s
    assert 'escapeHtml(data.thesis)' in s
    assert 'escapeHtml(data.notes)' in s


def test_listeners_are_delegated_on_the_container():
    """Per-element bindings would go stale on every Tabulator re-render."""
    s = _js()
    for event in ('pointerover', 'pointerout', 'click', 'keydown', 'focusin'):
        assert "container.addEventListener('%s'" % event in s


def test_hover_is_gated_on_a_mouse_pointer():
    """Touch taps must not fire a phantom hover."""
    assert "e.pointerType !== 'mouse'" in _js()


def test_card_is_mounted_on_the_body():
    """Tabulator cells are overflow:hidden — an in-cell card would be clipped."""
    assert 'document.body.appendChild(card)' in _js()


def test_escape_closes_and_returns_focus_to_the_trigger():
    s = _js()
    assert "e.key !== 'Escape'" in s
    assert 'trigger.focus()' in s


def test_card_is_announced_to_assistive_technology():
    s = _js()
    assert "setAttribute('role', 'dialog')" in s
    assert "'aria-label'" in s


def test_trigger_selector_matches_the_css_module():
    assert '.idea-thesis-cell.has-detail' in _js()


def test_focus_pin_is_suppressed_during_a_mouse_click():
    """The trigger is tabindex=0, so a click focuses it before the click fires.

    Order is pointerdown -> focus -> focusin -> pointerup -> click. Without a
    guard, focusin pins and the click toggles straight back off, so clicking
    a thesis cell would appear to do nothing.
    """
    s = _js()
    assert 'pointerDown = true;' in s
    assert re.search(r'if \(pinned \|\| pointerDown[^)]*\) return;', s), \
        'the focusin guard must still consult pointerDown'


def test_escape_refocus_cannot_re_pin_the_card():
    """Escape restores focus to the trigger, and focus() fires focusin.

    Without an explicit suppression flag that focusin re-pins the card that
    Escape just closed — the bug this guards against.
    """
    s = _js()
    assert 'suppressFocusPin' in s
    assert 'suppressFocusPin = true;' in s
    assert 'suppressFocusPin = false;' in s
