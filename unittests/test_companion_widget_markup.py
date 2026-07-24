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

"""Widget partial has no inline JS and exposes a config root (Task 1)."""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

WIDGET = os.path.join(
    os.path.dirname(__file__), '..',
    'app/templates/main/_companion_widget.html')


def test_widget_has_no_inline_script():
    html = open(WIDGET, encoding='utf-8').read()
    assert 'const CompanionChat' not in html, "inline JS must move to companion.js"


def test_widget_exposes_config_root():
    html = open(WIDGET, encoding='utf-8').read()
    assert 'id="companion-root"' in html
    assert 'data-endpoint-base' in html


if __name__ == '__main__':
    test_widget_has_no_inline_script()
    test_widget_exposes_config_root()
    print("PASS")
