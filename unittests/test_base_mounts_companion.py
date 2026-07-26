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

"""Base template mounts the companion widget behind an opt-in flag (Task 2)."""

import os

BASE = os.path.join(os.path.dirname(__file__), '..', 'app/templates/main/_base.html')
WIDGET = os.path.join(
    os.path.dirname(__file__), '..',
    'app/templates/main/_companion_widget.html')


def test_base_includes_companion_when_enabled():
    html = open(BASE, encoding='utf-8').read()
    assert 'companion_enabled' in html
    assert "_companion_widget.html" in html


def test_widget_guard_uses_companion_enabled():
    html = open(WIDGET, encoding='utf-8').read()
    assert 'companion_enabled' in html
    assert 'data-focus-type' in html


def test_companion_css_is_in_global_core_bundle():
    """The widget is global (in _base.html), so its CSS must be in css_core —
    not css_companies, or it won't style on portfolio/other pages."""
    src = open(os.path.join(os.path.dirname(__file__), '..', 'app/assets.py'),
               encoding='utf-8').read()
    core_section = src[src.index('css_core = Bundle('):src.index('css_companies = Bundle(')]
    assert "'css/modules/_companion.css'" in core_section


if __name__ == '__main__':
    test_base_includes_companion_when_enabled()
    test_widget_guard_uses_companion_enabled()
    print("PASS")
