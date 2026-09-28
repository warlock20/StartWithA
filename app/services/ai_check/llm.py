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

"""One place that talks to Claude for the AI check: params, pause handling, tool results, usage."""

from typing import Callable

from app.services.ai.prompt_service import prompt_service
from app.services.ai_check import AICheckError
from app.services.ai_check.pricing import estimate_cost

MAX_PAUSE_RESUMES = 3
FALLBACK_BETA = 'server-side-fallback-2026-07-01'

# A callable with the same shape as ClaudeProvider.create_message: one request in, the
# final message dict out. Lets callers (and later tasks) type-hint without importing the provider.
CreateMessage = Callable[[dict], dict]


def build_params(prompt_data, content, tools):
    """Request params for one stage. Non-standard fields go in extra_body so any SDK version passes them."""
    return {
        'model': prompt_data['model'],
        'max_tokens': prompt_data.get('max_tokens', 16000),
        'system': [{'type': 'text', 'text': prompt_data.get('system_context') or '',
                    'cache_control': {'type': 'ephemeral'}}],
        'messages': [{'role': 'user', 'content': content}],
        'tools': tools,
        'extra_headers': {'anthropic-beta': FALLBACK_BETA},
        'extra_body': {
            'fallbacks': 'default',
            'thinking': {'type': 'adaptive'},
            'output_config': {'effort': prompt_data.get('effort', 'medium')},
        },
    }


def call_claude(create_message, params, on_usage):
    """Send, resuming pause_turn up to MAX_PAUSE_RESUMES times. Returns (message, messages, responses)."""
    messages = list(params['messages'])
    responses = []
    for _ in range(MAX_PAUSE_RESUMES + 1):
        message = create_message({**params, 'messages': messages})
        responses.append(message)
        on_usage(message.get('model') or params['model'], message.get('usage') or {})
        stop = message.get('stop_reason')
        if stop == 'refusal':
            category = (message.get('stop_details') or {}).get('category') or 'unspecified'
            raise AICheckError(f'Claude declined this request (category: {category}).')
        if stop != 'pause_turn':
            return message, messages, responses
        messages = messages + [{'role': 'assistant', 'content': message.get('content') or []}]
    raise AICheckError(f'Claude kept pausing; gave up after {MAX_PAUSE_RESUMES} resumes.')


def _find_tool_call(message, names):
    for block in message.get('content') or []:
        if block.get('type') == 'tool_use' and block.get('name') in names:
            return block['name'], block.get('input') or {}
    return None


def call_for_tool(create_message, params, names, on_usage):
    """Run until Claude calls one of `names`; one reminder if it doesn't. Returns (name, input, responses)."""
    message, messages, responses = call_claude(create_message, params, on_usage)
    found = _find_tool_call(message, names)
    if found:
        return found[0], found[1], responses
    tool_names = ' or '.join(sorted(names))
    reminder = prompt_service.get_prompt('research', 'ai_check_tool_reminder', tool_names=tool_names)
    retry_params = {**params, 'messages': messages + [
        {'role': 'assistant', 'content': message.get('content') or []},
        {'role': 'user', 'content': reminder},
    ]}
    message, _, more = call_claude(create_message, retry_params, on_usage)
    responses += more
    found = _find_tool_call(message, names)
    if not found:
        raise AICheckError(f'Claude did not return a result through {tool_names}.')
    return found[0], found[1], responses


def record_usage(run, model_id, usage):
    """Add one response's usage and cost to the run (not committed)."""
    server = usage.get('server_tool_use') or {}
    run.tokens_in = (run.tokens_in or 0) + (usage.get('input_tokens') or 0) \
        + (usage.get('cache_read_input_tokens') or 0) + (usage.get('cache_creation_input_tokens') or 0)
    run.tokens_out = (run.tokens_out or 0) + (usage.get('output_tokens') or 0)
    run.cache_read_tokens = (run.cache_read_tokens or 0) + (usage.get('cache_read_input_tokens') or 0)
    run.web_searches = (run.web_searches or 0) + (server.get('web_search_requests') or 0)
    run.web_fetches = (run.web_fetches or 0) + (server.get('web_fetch_requests') or 0)
    run.cost_estimate = (run.cost_estimate or 0.0) + estimate_cost(model_id, usage)
