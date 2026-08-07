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


CSS = os.path.join(
    os.path.dirname(__file__), '..', 'app/static/css/modules/_idea-inbox.css')


def _css():
    return open(CSS, encoding='utf-8').read()


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
    # Without every reset, the flag sticks true and keyboard-arrival pinning
    # dies silently — the suite would stay green.
    for reset in ("document.addEventListener('pointerup'",
                  "document.addEventListener('pointercancel'",
                  "window.addEventListener('blur'"):
        assert reset in s, f'missing pointerDown reset: {reset}'


def test_escape_refocus_cannot_re_pin_the_card():
    """Escape restores focus to the trigger, and focus() fires focusin.

    Without an explicit suppression flag that focusin re-pins the card that
    Escape just closed — the bug this guards against.
    """
    s = _js()
    assert 'suppressFocusPin' in s
    assert 'suppressFocusPin = true;' in s
    assert 'suppressFocusPin = false;' in s


def test_scroll_region_is_capped_so_the_card_never_exceeds_the_viewport():
    assert 'max-height: 320px' in _css()


def test_trigger_signals_that_it_is_interactive():
    s = _css()
    assert '.idea-thesis-cell.has-detail' in s
    assert 'cursor: help' in s
    assert 'text-decoration-style: dotted' in s


def test_card_sits_below_the_bootstrap_modal_layer():
    """Bootstrap's modal backdrop is 1050 — the card must never cover it.

    Pin the invariant, not the literal. The exact value may legitimately move
    (it was raised from 1040 to clear the topbar and companion rail), but it
    must stay under the backdrop or the card floats over the evaluate modal.
    """
    match = re.search(r'\.thesis-card\s*\{[^}]*?z-index:\s*(\d+)', _css(), re.S)
    assert match, '.thesis-card must declare a z-index'
    z_index = int(match.group(1))
    assert 1040 <= z_index < 1050, (
        f'z-index {z_index} must clear the 1040 tier but stay below the 1050 backdrop')


def test_keyboard_focus_is_visible_on_the_trigger():
    assert ':focus-visible' in _css()


def test_motion_is_suppressed_when_the_user_asks_for_it():
    assert 'prefers-reduced-motion' in _css()


def test_scroll_region_is_keyboard_reachable():
    """A non-focusable scroll region cannot be scrolled by keyboard in Chromium.

    The card sits at the end of <body>, so Tab never reaches it either — focus
    has to be handed over explicitly when the content overflows.
    """
    s = _js()
    assert 'class="tc-scroll" tabindex="0"' in s
    assert 'scrollEl.focus();' in s
