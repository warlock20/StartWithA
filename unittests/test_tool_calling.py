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

"""Provider-agnostic tool-calling types + agentic loop (Tasks 3-5)."""

import inspect
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ai import ai_service
from app.services.ai.providers import claude as claude_module
from app.services.ai.providers.base import AIProvider
from app.services.ai.providers.claude import ClaudeProvider
from app.services.ai.providers.gemini import GeminiProvider
from app.services.ai.tool_calling import (
    ToolSpec, ToolCall, ToolResult, TurnResult, ToolLoopResult, run_tool_loop,
)


# --------------------------------------------------------------------------
# Task 3 — types
# --------------------------------------------------------------------------

def test_toolspec_roundtrips():
    spec = ToolSpec(name="ping", description="d", parameters={"type": "object", "properties": {}})
    assert spec.name == "ping"
    call = ToolCall(id="1", name="ping", arguments={})
    res = ToolResult(id="1", content="pong")
    assert res.id == call.id


# --------------------------------------------------------------------------
# Task 4 — the agentic loop (fake provider, no network)
# --------------------------------------------------------------------------

def _fake_provider(script):
    """A provider whose generate_turn returns scripted TurnResults in order.

    Its signature matches the provider contract (`AIProvider.generate_turn`), and it
    records the google_search flag each turn was asked for in `.google_search_seen`.
    """
    state = {'i': 0}

    class FakeProvider:
        google_search_seen = []

        def supports_tools(self):
            return True

        def generate_turn(self, messages, tools, system=None, max_tokens=1024,
                          temperature=0.3, google_search=False):
            self.google_search_seen.append(google_search)
            step = script[state['i']]
            state['i'] += 1
            return TurnResult(text=step.get('text'), tool_calls=step.get('tool_calls', []))

    return FakeProvider()


def test_loop_executes_tool_then_answers():
    provider = _fake_provider([
        {'tool_calls': [ToolCall(id='a', name='get', arguments={'x': 1})]},
        {'text': 'final answer'},
    ])
    seen = []

    def executor(call):
        seen.append(call.name)
        return ToolResult(id=call.id, content='DATA')

    result = run_tool_loop(provider, [{'role': 'user', 'content': 'q'}],
                           [ToolSpec('get', 'd', {'type': 'object', 'properties': {}})],
                           executor, max_hops=5)
    assert result.text == 'final answer'
    assert result.hops == 1
    assert seen == ['get']


def test_loop_stops_at_hop_cap():
    script = [{'tool_calls': [ToolCall(id=str(i), name='get', arguments={})]} for i in range(10)]
    script.append({'text': 'forced'})
    provider = _fake_provider(script)

    def executor(call):
        return ToolResult(id=call.id, content='D')

    result = run_tool_loop(provider, [{'role': 'user', 'content': 'q'}],
                           [ToolSpec('get', 'd', {'type': 'object', 'properties': {}})],
                           executor, max_hops=3)
    assert result.hops == 3  # capped


def test_loop_passes_google_search_to_every_turn():
    provider = _fake_provider([
        {'tool_calls': [ToolCall(id='a', name='get', arguments={})]},
        {'text': 'done'},
    ])
    run_tool_loop(provider, [{'role': 'user', 'content': 'q'}],
                  [ToolSpec('get', 'd', {'type': 'object', 'properties': {}})],
                  lambda c: ToolResult(id=c.id, content='D'), google_search=True)
    assert provider.google_search_seen == [True, True]


# --------------------------------------------------------------------------
# Provider contract — every tool-capable provider takes the loop's arguments
# --------------------------------------------------------------------------

@pytest.mark.parametrize('provider_cls', [AIProvider, ClaudeProvider, GeminiProvider])
def test_generate_turn_accepts_google_search(provider_cls):
    """run_tool_loop always passes google_search, so every provider must accept it."""
    assert 'google_search' in inspect.signature(provider_cls.generate_turn).parameters


class _FakeClaudeClient:
    """Stands in for anthropic.Anthropic: one scripted response per messages.create."""

    def __init__(self, responses):
        self.calls = []
        self._responses = list(responses)
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **params):
        self.calls.append(params)
        return SimpleNamespace(content=self._responses.pop(0))


def _claude_provider(monkeypatch, responses):
    monkeypatch.setattr(claude_module, '_anthropic_available', True)
    provider = ClaudeProvider()
    provider._client = _FakeClaudeClient(responses)
    return provider


@pytest.mark.usefixtures('app_context')
def test_loop_runs_on_claude(monkeypatch):
    """The companion routed to Claude used to crash: generate_turn rejected google_search."""
    provider = _claude_provider(monkeypatch, [
        [SimpleNamespace(type='tool_use', id='t1', name='get', input={'x': 1})],
        [SimpleNamespace(type='text', text='final answer')],
    ])
    result = run_tool_loop(provider, [{'role': 'user', 'content': 'q'}],
                           [ToolSpec('get', 'd', {'type': 'object', 'properties': {}})],
                           lambda c: ToolResult(id=c.id, content='DATA'))
    assert result.text == 'final answer'
    assert result.hops == 1
    assert len(provider._client.calls) == 2


@pytest.mark.usefixtures('app_context')
def test_claude_refuses_google_search(monkeypatch):
    """Claude has no Google Search grounding; asking for it must fail, not answer ungrounded."""
    provider = _claude_provider(monkeypatch, [[SimpleNamespace(type='text', text='x')]])
    with pytest.raises(NotImplementedError, match='Google Search'):
        provider.generate_turn([{'role': 'user', 'content': 'q'}], [], google_search=True)
    assert provider._client.calls == []


# --------------------------------------------------------------------------
# Task 5 — ai_service.generate_with_tools routing
# --------------------------------------------------------------------------

def test_ai_service_generate_with_tools_routes(monkeypatch):
    fake = _fake_provider([{'text': 'ok'}])
    monkeypatch.setattr(ai_service, '_get_provider', lambda *a, **k: fake)
    out = ai_service.generate_with_tools(
        [{'role': 'user', 'content': 'hi'}],
        [ToolSpec('t', 'd', {'type': 'object', 'properties': {}})],
        lambda c: ToolResult(id=c.id, content='x'))
    assert out.text == 'ok'


def test_ai_service_rejects_provider_without_tools(monkeypatch):

    class NoTools:
        def supports_tools(self):
            return False
        model_name = 'no-tools'

    monkeypatch.setattr(ai_service, '_get_provider', lambda *a, **k: NoTools())
    try:
        ai_service.generate_with_tools([{'role': 'user', 'content': 'hi'}], [],
                                       lambda c: ToolResult(id=c.id, content='x'))
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert 'tool' in str(e).lower()


if __name__ == '__main__':
    test_toolspec_roundtrips()
    test_loop_executes_tool_then_answers()
    test_loop_stops_at_hop_cap()
    print("PASS (loop tests; pytest for monkeypatch tests)")
