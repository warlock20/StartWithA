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

"""Citations — showing where an answer came from.

Two layers, and only the first is guaranteed. The executor records every source it
reads while answering, which is a fact and cannot be wrong. On top of that the model
may mark claims with [n]; sparse marking is normal, not a failure, because the
source list stands on its own. A marker pointing at nothing is stripped.
"""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.dirname(__file__))

from companion_js import companion_js

from app.services.ai.tool_calling import ToolCall, ToolLoopResult
from app.services.argos import agent as agent_mod
from app.services.argos.agent import CompanionAgent, strip_unresolved_citations
from app.services.argos.tools import ToolExecutor


def _call(name, **arguments):
    return ToolCall(id='c1', name=name, arguments=arguments)


def test_reading_a_company_registers_one_source(app_context, seed_company_with_findings):
    user_id, company_id = seed_company_with_findings
    executor = ToolExecutor(user_id)
    executor(_call('get_company_context', company_id=company_id))

    assert len(executor.sources) == 1
    source = executor.sources[0]
    assert source['n'] == 1
    assert source['source_type'] == 'company'
    assert source['source_id'] == company_id
    assert source['label']


def test_the_model_sees_the_citation_number(app_context, seed_company_with_findings):
    """Numbers have to be in the tool result, or the model can't cite them."""
    user_id, company_id = seed_company_with_findings
    executor = ToolExecutor(user_id)
    result = executor(_call('get_company_context', company_id=company_id))
    assert json.loads(result.content).get('citation') == 1


def test_reading_the_same_source_twice_reuses_its_number(app_context,
                                                         seed_company_with_findings):
    user_id, company_id = seed_company_with_findings
    executor = ToolExecutor(user_id)
    executor(_call('get_company_context', company_id=company_id))
    executor(_call('get_company_context', company_id=company_id))

    assert len(executor.sources) == 1
    assert [s['n'] for s in executor.sources] == [1]


def test_each_knowledge_result_gets_its_own_number(app_context, stub_embedding,
                                                   seed_many_chunks):
    executor = ToolExecutor(seed_many_chunks)
    result = executor(_call('search_my_knowledge', query='competitive moat advantage'))
    payload = json.loads(result.content)

    numbers = [r['citation'] for r in payload['results']]
    assert numbers == sorted(set(numbers)), 'numbers must be unique and ordered'
    assert len(executor.sources) == len(payload['results'])


def test_an_unowned_company_registers_no_source(app_context, seed_two_users):
    """A denied read is not a source."""
    u1_id, _u2_id, u2_company_id = seed_two_users
    executor = ToolExecutor(u1_id)
    executor(_call('get_company_context', company_id=u2_company_id))
    assert executor.sources == []


def test_phantom_markers_are_stripped():
    text = 'Recurring revenue is 86%[1], tenure is 12 years[4].'
    assert strip_unresolved_citations(text, {1, 2, 3}) == (
        'Recurring revenue is 86%[1], tenure is 12 years.')


def test_unmarked_claims_are_left_alone():
    """Sparse marking is the normal case — the source list carries the rest."""
    text = 'Recurring revenue is 86%. Tenure is 12 years[2].'
    assert strip_unresolved_citations(text, {1, 2}) == text


def test_js_renders_the_deep_dive_split():
    """Answer and its numbered sources side by side, with the actions."""
    js = companion_js()
    assert 'setDeep' in js
    assert 'companionDeep' in js
    assert 'Insert into checklist' in js
    assert 'Export' in js


def test_js_links_markers_to_source_cards():
    """A [n] in the answer should reach its card; sources render even unmarked."""
    js = companion_js()
    assert 'renderSources' in js
    assert 'linkCitations' in js


def test_widget_has_the_deep_dive_mount():
    html = open(os.path.join(os.path.dirname(__file__), '..',
                             'app/templates/main/_companion_widget.html'),
                encoding='utf-8').read()
    assert 'id="companionDeep"' in html
    assert 'id="companionDeepToggle"' in html


def test_ask_returns_the_sources_it_read(monkeypatch, app_context,
                                         seed_company_with_findings):
    user_id, company_id = seed_company_with_findings

    def fake_generate_with_tools(messages, tools, executor, system=None, **kwargs):
        # Simulate the model reading the company, then citing it plus a phantom.
        executor(_call('get_company_context', company_id=company_id))
        return ToolLoopResult(
            text='Switching costs look high[1], and tenure is long[9].', hops=1, calls=[])

    monkeypatch.setattr(agent_mod.ai_service, 'generate_with_tools',
                        fake_generate_with_tools)

    out = CompanionAgent(user_id).ask('are switching costs high?', [], {})

    assert [s['n'] for s in out['sources']] == [1]
    assert out['sources'][0]['source_type'] == 'company'
    assert '[1]' in out['answer']
    assert '[9]' not in out['answer'], 'a marker pointing at nothing must be stripped'
