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

"""Target pages set companion_focus; the widget is now global (no per-page flag)."""

import os

ROOT = os.path.join(os.path.dirname(__file__), '..')

CASES = [
    ('app/companies/templates/company_detail.html', "'company'"),
    ('app/portfolio/templates/portfolio_dashboard.html', "'portfolio'"),
    ('app/research_workflow/templates/execute_step.html', "'research'"),
]


def test_target_pages_set_focus_without_flag():
    for path, focus_type in CASES:
        html = open(os.path.join(ROOT, path), encoding='utf-8').read()
        normalised = html.replace(' ', '')
        assert 'companion_enabled=true' not in normalised, f"{path}: flag should be gone (widget is global)"
        assert 'companion_focus' in html, f"{path}: missing companion_focus"
        assert focus_type in html, f"{path}: missing focus type {focus_type}"


if __name__ == '__main__':
    test_target_pages_set_focus_without_flag()
    print("PASS")
