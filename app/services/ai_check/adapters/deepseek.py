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

"""AI check calls on DeepSeek (OpenAI-compatible API): text only, no web search.

DeepSeek V4 runs in thinking mode and rejects a forced tool_choice, so tool_choice is never sent;
the shared reminder in llm.call_for_tool covers a turn that ends without a tool call."""

import json

import openai

from app.services.ai.config import get_ai_config
from app.services.ai.providers.deepseek import DEEPSEEK_BASE_URL
from app.services.ai_check import AICheckError
from app.services.ai_check.adapters.base import ProviderAdapter
from app.services.ai_check.llm import StageReply, Usage


def deepseek_usage(response, model):
    usage = response.usage
    if usage is None:
        return Usage(model=model)
    hit = getattr(usage, 'prompt_cache_hit_tokens', None) or 0
    return Usage(model=model, tokens_in=(usage.prompt_tokens or 0) - hit,
                 tokens_out=usage.completion_tokens or 0, cached_in=hit)


class DeepSeekAdapter(ProviderAdapter):
    provider = 'deepseek'
    name = 'DeepSeek'

    def _make_client(self):
        key = get_ai_config().deepseek_api_key
        return openai.OpenAI(api_key=key, base_url=DEEPSEEK_BASE_URL) if key else None

    def _first_turn(self, call):
        text = '\n\n'.join([document.as_text for document in call.documents] + [call.text])
        return [{'role': 'system', 'content': call.system}, {'role': 'user', 'content': text}]

    def _append_user(self, transcript, text):
        return transcript + [{'role': 'user', 'content': text}]

    def _complete(self, call, messages, on_usage):
        tools = [{'type': 'function', 'function': {'name': tool['name'], 'description': tool['description'],
                                                   'parameters': tool['input_schema']}}
                 for tool in call.tools]
        try:
            response = self.client().chat.completions.create(
                model=call.model, messages=messages, tools=tools, max_tokens=call.max_tokens)
        except openai.BadRequestError as exc:
            raise AICheckError(f'DeepSeek rejected the request: {exc.message}') from exc
        usage = deepseek_usage(response, call.model)
        on_usage(usage)
        choice = response.choices[0]
        if choice.finish_reason == 'length':
            raise AICheckError("DeepSeek's answer was cut off (output limit reached).")
        if choice.finish_reason == 'content_filter':
            raise AICheckError('DeepSeek declined this request (content filter).')
        if choice.finish_reason == 'insufficient_system_resource':
            raise RuntimeError('DeepSeek is overloaded.')  # not an AICheckError: the task retries
        message = choice.message
        name, args = None, {}
        if message.tool_calls:
            function = message.tool_calls[0].function
            try:
                name, args = function.name, json.loads(function.arguments or '{}')
            except json.JSONDecodeError:
                name, args = None, {}
        transcript = messages + [{'role': 'assistant', 'content': message.content or ''}]
        return StageReply(name, args, transcript, [usage])
