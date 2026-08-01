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

"""Selection assist — evidence for highlighted text.

Retrieval only: no LLM, no tokens. The user selects a phrase, and the companion
offers what their *own* knowledge already says about it. Quiet by design — weak
matches produce nothing rather than a popover full of noise.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.dirname(__file__))

from companion_js import companion_js

from app import db
from app.models.knowledge_chunk import KnowledgeChunk
from app.services.argos.selection_assist import MIN_SELECTION_CHARS, find_evidence_for_selection



def _chunk_summaries(evidence):
    return [e['summary'] for e in evidence]


def test_short_selections_are_ignored(app_context, stub_embedding, seed_many_chunks):
    """A stray click or a two-word highlight shouldn't fire retrieval at all."""
    assert find_evidence_for_selection(seed_many_chunks, 'moat') == []
    assert find_evidence_for_selection(seed_many_chunks, '   ') == []
    assert len(' ' * MIN_SELECTION_CHARS) >= MIN_SELECTION_CHARS  # constant is exported


def test_returns_the_users_own_evidence(app_context, stub_embedding, seed_many_chunks):
    evidence = find_evidence_for_selection(
        seed_many_chunks, 'the competitive moat and advantage of this business')
    assert evidence, 'expected some evidence from the user own chunks'
    for item in evidence:
        assert set(item) >= {'source_type', 'source_id', 'title', 'summary', 'score'}


def test_never_returns_another_users_evidence(app_context, stub_embedding,
                                              seed_many_chunks, other_user):
    """Ownership is enforced in the query, not filtered afterwards."""
    evidence = find_evidence_for_selection(
        other_user, 'the competitive moat and advantage of this business')
    assert evidence == []


def test_result_count_is_small_enough_for_a_popover(app_context, stub_embedding,
                                                    seed_many_chunks):
    """A popover is not a search results page — three items at most."""
    evidence = find_evidence_for_selection(
        seed_many_chunks, 'the competitive moat and advantage of this business')
    assert len(evidence) <= 3


def test_weak_matches_are_dropped(app_context, stub_embedding, seed_many_chunks,
                                  monkeypatch):
    """Below the relevance floor the companion stays silent."""
    import app.services.argos.selection_assist as mod
    monkeypatch.setattr(mod, 'MIN_RELEVANCE', 2.0)   # nothing can score this high
    evidence = find_evidence_for_selection(
        seed_many_chunks, 'the competitive moat and advantage of this business')
    assert evidence == []


def test_endpoint_requires_login(_app):
    resp = _app.test_client().post('/companion/selection', json={'text': 'x' * 40})
    assert resp.status_code in (302, 401)


def test_endpoint_returns_evidence(client_logged_in, stub_embedding):
    client, user_id = client_logged_in
    db.session.add(KnowledgeChunk(
        user_id=user_id, company_id=None, source_type='journal', source_id=1,
        title='Switching costs note',
        summary='CATIA is embedded in aerospace pipelines, so customers rarely leave.',
        embedding=stub_embedding.embed(
            'CATIA is embedded in aerospace pipelines, so customers rarely leave.'),
        token_estimate=20))
    db.session.commit()

    resp = client.post('/companion/selection',
                       json={'text': 'switching costs keep customers locked in'})
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload['success'] is True
    assert 'evidence' in payload['data']


def test_endpoint_rejects_an_empty_selection(client_logged_in):
    client, _ = client_logged_in
    resp = client.post('/companion/selection', json={'text': '  '})
    assert resp.status_code == 400


def test_js_offers_evidence_on_selection():
    """The popover is wired to selection, and can put a citation in the editor."""
    s = companion_js()
    assert 'selectionchange' in s or 'mouseup' in s
    assert '/selection' in s
    assert 'companionSelectionPopover' in s
    assert 'Insert citation' in s


def test_js_ignores_selections_inside_the_rail():
    """Selecting the companion's own answer must not offer evidence about itself."""
    s = companion_js()
    assert 'companionRail' in s
    assert 'closest' in s
