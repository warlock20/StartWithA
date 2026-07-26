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

"""Issue #300: companion enabled on the three target pages (Task 16)."""

import os

ROOT = os.path.join(os.path.dirname(__file__), '..')

CASES = [
    ('app/companies/templates/company_detail.html', "'company'"),
    ('app/portfolio/templates/portfolio_dashboard.html', "'portfolio'"),
    # research step pages were enabled in Task 2
    ('app/research_workflow/templates/execute_step.html', "'research'"),
]


def test_target_pages_enable_companion():
    for path, focus_type in CASES:
        html = open(os.path.join(ROOT, path), encoding='utf-8').read()
        normalised = html.replace(' ', '')
        assert 'companion_enabled=true' in normalised, f"{path}: companion not enabled"
        assert focus_type in html, f"{path}: missing focus type {focus_type}"


if __name__ == '__main__':
    test_target_pages_enable_companion()
    print("PASS")
