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

"""Tool schemas + ownership-bound ToolExecutor (Task 10). DB-backed."""

import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ai.tool_calling import ToolCall
from app.services.argos.tools import COMPANION_TOOLS, ToolExecutor


def test_tool_registry_has_six_tools():
    names = {t.name for t in COMPANION_TOOLS}
    assert names == {
        'get_portfolio_overview', 'get_company_context', 'get_research_project',
        'search_my_knowledge', 'get_resource', 'get_mistakes_and_patterns',
    }


def test_executor_denies_foreign_company(app_context, seed_two_users):
    u1, u2, u2_company = seed_two_users
    result = ToolExecutor(user_id=u1)(
        ToolCall(id='1', name='get_company_context', arguments={'company_id': u2_company}))
    payload = json.loads(result.content)
    assert 'error' in payload  # ownership denied, no data leaked


def test_executor_unknown_tool(app_context, seed_two_users):
    u1, _, _ = seed_two_users
    result = ToolExecutor(user_id=u1)(ToolCall(id='1', name='nope', arguments={}))
    assert 'unknown tool' in result.content.lower()


def test_executor_runs_owned_company(app_context, seed_company_no_project):
    uid, cid = seed_company_no_project
    result = ToolExecutor(user_id=uid)(
        ToolCall(id='1', name='get_company_context', arguments={'company_id': cid}))
    payload = json.loads(result.content)
    assert payload['company_id'] == cid
