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

"""AI check calls on Gemini (google-genai): inline PDFs, Google Search with function calls."""

from google.genai import errors as genai_errors
from google.genai import types as genai_types

from app.services.ai.providers.gemini import _get_gemini_client
from app.services.ai_check import AICheckError
from app.services.ai_check.adapters.base import ProviderAdapter
from app.services.ai_check.llm import StageReply, Usage

TRUNCATED = {'MAX_TOKENS'}
BLOCKED = {'SAFETY', 'RECITATION', 'BLOCKLIST', 'PROHIBITED_CONTENT', 'SPII', 'IMAGE_SAFETY'}
THINKING_LEVELS = {'low': 'LOW', 'medium': 'MEDIUM', 'high': 'HIGH'}


def _name(value):
    return getattr(value, 'name', None) or str(value or '')


def gemini_usage(response, model):
    meta = response.usage_metadata
    prompt = (meta.prompt_token_count or 0) if meta else 0
    cached = (meta.cached_content_token_count or 0) if meta else 0
    searches = sum(len(c.grounding_metadata.web_search_queries or [])
                   for c in response.candidates or [] if c.grounding_metadata)
    return Usage(
        model=model,
        tokens_in=prompt - cached + ((meta.tool_use_prompt_token_count or 0) if meta else 0),
        tokens_out=((meta.candidates_token_count or 0) + (meta.thoughts_token_count or 0)) if meta else 0,
        cached_in=cached, searches=searches)


class GeminiAdapter(ProviderAdapter):
    provider = 'gemini'
    name = 'Gemini'
    can_search = True

    def _make_client(self):
        return _get_gemini_client()

    def _config(self, call):
        tools = []
        if call.search_cap is not None:
            tools.append(genai_types.Tool(google_search=genai_types.GoogleSearch()))
        tools.append(genai_types.Tool(function_declarations=[
            genai_types.FunctionDeclaration(name=tool['name'], description=tool['description'],
                                            parameters_json_schema=tool['input_schema'])
            for tool in call.tools]))
        config = {'system_instruction': call.system, 'max_output_tokens': call.max_tokens, 'tools': tools}
        if call.model.startswith('gemini-3'):
            config['thinking_config'] = {'thinking_level': THINKING_LEVELS.get(call.effort, 'HIGH')}
        if call.search_cap is not None:
            # Built-in search plus functions in one request: Gemini 3 only, and `auto` mode is refused.
            # Gemini has no per-call search cap; run_gather's budget check bounds it per pass.
            config['tool_config'] = {'function_calling_config': {'mode': 'VALIDATED'},
                                     'include_server_side_tool_invocations': True}
        return config

    def _first_turn(self, call):
        parts = []
        for document in call.documents:
            if document.kind == 'pdf':
                with open(document.path, 'rb') as handle:
                    parts.append(genai_types.Part.from_bytes(data=handle.read(), mime_type='application/pdf'))
            else:
                parts.append(genai_types.Part(text=document.as_text))
        parts.append(genai_types.Part(text=call.text))
        return [genai_types.Content(role='user', parts=parts)]

    def _append_user(self, transcript, text):
        return transcript + [genai_types.Content(role='user', parts=[genai_types.Part(text=text)])]

    def _complete(self, call, contents, on_usage):
        try:
            response = self.client().models.generate_content(
                model=call.model, contents=contents, config=self._config(call))
        except genai_errors.ClientError as exc:
            if exc.code == 429:
                raise  # rate limit: let the Celery task retry
            raise AICheckError(f'Gemini rejected the request: {exc.message}') from exc
        usage = gemini_usage(response, call.model)
        on_usage(usage)
        feedback = response.prompt_feedback
        if feedback is not None and feedback.block_reason:
            raise AICheckError(f'Gemini blocked this request (category: {_name(feedback.block_reason).lower()}).')
        if not response.candidates:
            raise AICheckError('Gemini returned no answer.')
        candidate = response.candidates[0]
        reason = _name(candidate.finish_reason)
        if reason in TRUNCATED:
            raise AICheckError("Gemini's answer was cut off (output limit reached).")
        if reason in BLOCKED:
            raise AICheckError(f'Gemini blocked this request (category: {reason.lower()}).')
        name, args = None, {}
        for part in (candidate.content.parts if candidate.content else None) or []:
            if part.function_call:
                name, args = part.function_call.name, dict(part.function_call.args or {})
                break
        # Replay the model turn exactly as sent (thought signatures included) for the reminder.
        transcript = contents + ([candidate.content] if candidate.content else [])
        return StageReply(name, args, transcript, [usage])
