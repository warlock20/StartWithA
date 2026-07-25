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

"""
CompanionAgent — the global agentic companion.

Assembles the account map (cheap DB skeleton) + focus into the system prompt,
offers the tool menu, and runs the tool-calling loop via ai_service. The model
decides which tools to call and chains them; every answer is grounded in the
user's own data. Facts-only compliance rules live in companion_agent.yaml.
"""

import logging

from app.services.ai import ai_service
from app.services.ai.prompt_service import prompt_service, resolve_model_provider
from app.services.argos.account_map import build_account_map, render_account_map
from app.services.argos.tools import COMPANION_TOOLS, ToolExecutor

logger = logging.getLogger(__name__)

_MAX_HOPS = 5


class CompanionAgent:
    """One instance per user; ``ask`` answers a question grounded in their account."""

    def __init__(self, user_id):
        self.user_id = user_id

    def ask(self, question, history=None, focus=None):
        """
        Answer a question using account map + tools.

        Returns {'answer': str, 'hops': int, 'tool_calls': [tool names]}.
        """
        account_map = build_account_map(self.user_id, focus)

        prompt_data = prompt_service.get_prompt_with_metadata(
            'companion', 'companion_agent',
            account_map=render_account_map(account_map),
            focus=str(focus or {}),
        )
        metadata = prompt_data.get('metadata', {})
        system = prompt_data['prompt']
        model_enum, provider_enum = resolve_model_provider(
            metadata, user_id=self.user_id, prompt_category='companion')

        messages = [
            {'role': m['role'], 'content': m['content']}
            for m in (history or [])[-10:]
        ]
        messages.append({'role': 'user', 'content': question})

        result = ai_service.generate_with_tools(
            messages,
            COMPANION_TOOLS,
            ToolExecutor(self.user_id),
            system=system,
            provider=provider_enum,
            model=model_enum,
            max_hops=_MAX_HOPS,
            max_tokens=metadata.get('max_tokens', 4096),
            temperature=metadata.get('temperature', 0.3),
        )
        return {
            'answer': result.text,
            'hops': result.hops,
            'tool_calls': [c.name for c in result.calls],
        }
