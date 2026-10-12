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

"""AI check calls on Claude: Messages API params, pause_turn resumes, refusal and truncation."""

import base64

from app.services.ai.providers.claude import ClaudeProvider
from app.services.ai_check import AICheckError
from app.services.ai_check.llm import StageReply, Usage
from app.services.ai_check.verify import fetched_texts

MAX_PAUSE_RESUMES = 3
FALLBACK_BETA = 'server-side-fallback-2026-07-01'
TRUNCATION_ERRORS = {
    'max_tokens': "Claude's answer was cut off (output limit reached).",
    'model_context_window_exceeded': 'The source was too large for Claude to read in one request.',
}


def claude_usage(message, default_model):
    usage = message.get('usage') or {}
    server = usage.get('server_tool_use') or {}
    return Usage(model=message.get('model') or default_model,
                 tokens_in=usage.get('input_tokens') or 0, tokens_out=usage.get('output_tokens') or 0,
                 cached_in=usage.get('cache_read_input_tokens') or 0,
                 cache_write=usage.get('cache_creation_input_tokens') or 0,
                 searches=server.get('web_search_requests') or 0,
                 fetches=server.get('web_fetch_requests') or 0)


def _document_block(document):
    if document.kind == 'pdf':
        with open(document.path, 'rb') as handle:
            data = base64.standard_b64encode(handle.read()).decode('ascii')
        return {'type': 'document', 'title': document.title,
                'source': {'type': 'base64', 'media_type': 'application/pdf', 'data': data}}
    return {'type': 'document', 'title': document.title,
            'source': {'type': 'text', 'media_type': 'text/plain', 'data': '\n'.join(document.page_texts)}}


def _find_tool_call(message):
    for block in message.get('content') or []:
        if block.get('type') == 'tool_use':
            return block.get('name'), block.get('input') or {}
    return None, {}


class ClaudeAdapter:
    provider = 'claude'

    def __init__(self, create_message=None):
        """`create_message` sends one params dict and returns the final message as a dict
        (ClaudeProvider.create_message's shape). Tests inject a scripted one."""
        self._create_message = create_message

    def _send(self, params):
        if self._create_message is None:
            provider = ClaudeProvider()
            if not provider.is_available():
                raise AICheckError('Claude is not configured on the server.')
            self._create_message = provider.create_message
        return self._create_message(params)

    def _params(self, call, messages):
        tools = list(call.tools)
        if call.fetch_cap is not None:
            tools.insert(0, {'type': 'web_fetch_20260209', 'name': 'web_fetch', 'max_uses': call.fetch_cap})
        if call.search_cap is not None:
            tools.insert(0, {'type': 'web_search_20260209', 'name': 'web_search', 'max_uses': call.search_cap})
        return {
            'model': call.model,
            'max_tokens': call.max_tokens,
            'system': [{'type': 'text', 'text': call.system, 'cache_control': {'type': 'ephemeral'}}],
            'messages': messages,
            'tools': tools,
            # Non-standard fields go in extra_body so any SDK version passes them.
            'extra_headers': {'anthropic-beta': FALLBACK_BETA},
            'extra_body': {
                'fallbacks': 'default',
                'thinking': {'type': 'adaptive'},
                'output_config': {'effort': call.effort},
            },
        }

    def send(self, call, on_usage):
        if call.documents:
            content = [_document_block(doc) for doc in call.documents] + [{'type': 'text', 'text': call.text}]
        else:
            content = call.text
        return self._run(call, [{'role': 'user', 'content': content}], on_usage)

    def follow_up(self, call, transcript, text, on_usage):
        return self._run(call, transcript + [{'role': 'user', 'content': text}], on_usage)

    def _run(self, call, messages, on_usage):
        """Send, resuming pause_turn up to MAX_PAUSE_RESUMES times."""
        usages, responses = [], []
        for _ in range(MAX_PAUSE_RESUMES + 1):
            message = self._send(self._params(call, messages))
            responses.append(message)
            usage = claude_usage(message, call.model)
            usages.append(usage)
            on_usage(usage)
            stop = message.get('stop_reason')
            if stop == 'refusal':
                category = (message.get('stop_details') or {}).get('category') or 'unspecified'
                raise AICheckError(f'Claude declined this request (category: {category}).')
            if stop in TRUNCATION_ERRORS:
                raise AICheckError(TRUNCATION_ERRORS[stop])
            messages = messages + [{'role': 'assistant', 'content': message.get('content') or []}]
            if stop != 'pause_turn':
                name, args = _find_tool_call(message)
                return StageReply(name, args, messages, usages, fetched_texts=fetched_texts(responses))
        raise AICheckError(f'Claude kept pausing; gave up after {MAX_PAUSE_RESUMES} resumes.')
