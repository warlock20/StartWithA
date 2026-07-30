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

"""Project-free company context for the companion (Task 11). DB-backed."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.argos.core import ArgosService


def test_build_company_context_without_project(app_context, seed_company_no_project):
    uid, cid = seed_company_no_project
    summary = ArgosService(uid).build_company_context(cid).to_summary()

    assert summary['company_id'] == cid
    assert 'position' in summary
    assert summary['position'] is None  # not held


def test_build_company_context_with_held_position(app_context, seed_portfolio_with_history):
    uid, cid = seed_portfolio_with_history
    summary = ArgosService(uid).build_company_context(cid).to_summary()

    assert summary['company_id'] == cid
    assert isinstance(summary['position'], dict)
    assert 'days_held' in summary['position']


def test_build_company_context_uses_completed_project(app_context, seed_company_completed_project):
    uid, cid = seed_company_completed_project
    summary = ArgosService(uid).build_company_context(cid).to_summary()

    assert summary['latest_decision'] == 'invest'
    assert 'completed' in summary['project_state']
    assert 'high debt load' in summary['red_flags']
    assert summary['investment_thesis'] == 'Durable moat with pricing power.'
