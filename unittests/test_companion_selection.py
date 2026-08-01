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
from app.services.argos import selection_assist
from app.services.argos.knowledge_index import _summarise
from app.services.argos.selection_assist import (
    MIN_RELEVANCE, MIN_SELECTION_CHARS, find_evidence_for_selection)
from app.utils.blocknote_utils import blocknote_to_text


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
    monkeypatch.setattr(selection_assist, 'MIN_RELEVANCE', 2.0)   # nothing can score this high
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


def test_relevance_floor_clears_the_measured_noise_band():
    """The floor was measured against a real account, not guessed.

    With Gemini embeddings unrelated text still scores ~0.56-0.62 (gibberish once
    beat a genuine query), while relevant text starts around 0.64. A floor inside
    the noise band makes the popover fire on everything, which is worse than
    silence. Re-measure if the embedding model ever changes.
    """
    assert MIN_RELEVANCE > 0.623, 'floor must clear the measured noise ceiling'
    assert MIN_RELEVANCE < 0.640, 'floor must stay under the weakest real match'


def test_company_scope_falls_back_to_the_whole_account(app_context, stub_embedding,
                                                       seed_many_chunks):
    """Regression: scoping hard to the page's company made this silent forever.

    Knowledge is indexed per company, so on a company with nothing written about
    it yet — where you are most likely to be reading something new — a hard filter
    matches nothing. The company is a preference; the account is the fallback.
    """
    user_id = seed_many_chunks
    # 999 owns no chunks, so a hard scope would return nothing at all.
    evidence = find_evidence_for_selection(
        user_id, 'the competitive moat and advantage of this business', company_id=999)
    assert evidence, 'expected a fallback to account-wide evidence'


def test_blocknote_journal_content_is_flattened_before_indexing():
    """Regression: journal entries are BlockNote JSON, and were indexed verbatim.

    That embedded the editor's markup — block ids, props, textColor — diluting the
    vector and showing raw JSON to the reader in the evidence popover.
    """
    raw = ('[{"id":"efa72e0e","type":"paragraph","props":{"textColor":"default"},'
           '"content":[{"type":"text","text":"Aumann raised its dividend"}]}]')
    out = _summarise(1, 'journal', raw)
    assert out == 'Aumann raised its dividend'
    assert 'textColor' not in out and '"type"' not in out


def test_plain_text_passes_through_the_flattener():
    assert _summarise(1, 'journal', 'a plain note') == 'a plain note'


def test_flattener_keeps_link_text_and_nested_blocks():
    """Regression: a paragraph whose only content is a link flattened to nothing.

    That left the entry unindexable, and because _upsert skips empty summaries the
    stale pre-fix row survived re-indexing with raw JSON still in it.
    """
    doc = ('[{"type":"paragraph","content":[{"type":"link","href":"https://x.test",'
           '"content":[{"type":"text","text":"Vidrala annual report"}]}]},'
           '{"type":"bulletListItem","content":[{"type":"text","text":"parent"}],'
           '"children":[{"type":"bulletListItem",'
           '"content":[{"type":"text","text":"nested point"}]}]}]')
    out = blocknote_to_text(doc)
    assert 'Vidrala annual report' in out
    assert 'nested point' in out


def test_flattener_still_handles_plain_and_html():
    assert blocknote_to_text('just text') == 'just text'
    assert blocknote_to_text('<p>old quill</p>') == 'old quill'
