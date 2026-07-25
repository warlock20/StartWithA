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

"""CompanionAgent wiring account map + tools + loop (Task 12). DB-backed."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.argos import agent as agent_mod
from app.services.argos.agent import CompanionAgent
from app.services.ai.tool_calling import ToolLoopResult


def test_agent_ask_assembles_system_tools_and_messages(monkeypatch, app_context, seed_portfolio):
    captured = {}

    def fake_generate_with_tools(messages, tools, executor, system=None, **kwargs):
        captured['system'] = system
        captured['tools'] = tools
        captured['messages'] = messages
        return ToolLoopResult(text='the answer', hops=1, calls=[])

    monkeypatch.setattr(agent_mod.ai_service, 'generate_with_tools', fake_generate_with_tools)

    out = CompanionAgent(seed_portfolio).ask('what did I miss?', [], {'type': 'portfolio'})

    assert out['answer'] == 'the answer'
    assert out['hops'] == 1
    # Facts-only compliance rules must be in the system prompt.
    assert 'opinions are yours' in captured['system'].lower()
    # The account map (holdings) must be embedded in the system prompt.
    assert 'portfolio' in captured['system'].lower()
    # All six tools offered.
    assert len(captured['tools']) == 6
    # The user's question is the final message.
    assert captured['messages'][-1] == {'role': 'user', 'content': 'what did I miss?'}
