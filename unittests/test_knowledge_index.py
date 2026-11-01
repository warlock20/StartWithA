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

"""Knowledge index: split, contextualize, embed, skip unchanged, clean up (#389). DB-backed."""

import json
import os
import re
import sys
import zlib
from datetime import date, datetime, timedelta

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import db
from app.models import CompanyResource, User
from app.models.idea_pipeline import MistakeLog
from app.models.journal import DecisionJournal, JournalEntry
from app.models.knowledge_chunk import KnowledgeChunk
from app.services.argos import knowledge_context, knowledge_index
from app.services.argos.knowledge_index import IndexUnavailable, index_user_knowledge
from app.services.argos.knowledge_search import search_my_knowledge
from app.services.findings import add_finding
from app.utils.blocknote_utils import blocknote_to_text
from app.utils.time_utils import now_utc
from conftest import _make_chunk, _make_company, _make_user

LLM_CONTEXT = 'From a note on the company.'


def _sentences(count, prefix='s'):
    return ' '.join(f'{prefix}{i} ' + ' '.join(f'w{i}x{j}' for j in range(8)) + ' end.' for i in range(count))


@pytest.fixture
def embed_calls(stub_embedding, monkeypatch):
    """Count embedding calls made through the stub."""
    calls = []
    original = stub_embedding.embed

    def counting(text, use_cache=True):
        calls.append(text)
        return original(text, use_cache)

    monkeypatch.setattr(stub_embedding, 'embed', counting)
    return calls


@pytest.fixture
def llm_calls(monkeypatch):
    calls = []

    def fake_generate_text(prompt, **kwargs):
        calls.append(prompt)
        return LLM_CONTEXT

    monkeypatch.setattr(knowledge_context.ai_service, 'generate_text', fake_generate_text)
    return calls


@pytest.fixture
def llm_down(monkeypatch):
    calls = []

    def fail(prompt, **kwargs):
        calls.append(prompt)
        raise RuntimeError('provider unreachable')

    monkeypatch.setattr(knowledge_context.ai_service, 'generate_text', fail)
    return calls


@pytest.fixture
def keyword_embedding(monkeypatch):
    """Hashed bag of words: texts sharing words get similar vectors."""
    class _KeywordEmbedding:
        model_id = 'keyword-embedding'
        dimension = 768

        def embed(self, text, use_cache=True):
            vec = np.zeros(768)
            for word in re.findall(r'[\w.%]+', text.lower()):
                vec[zlib.crc32(word.encode()) % 768] += 1.0
            return vec

    fake = _KeywordEmbedding()
    for modpath in ('app.services.argos.knowledge_index', 'app.services.argos.knowledge_search'):
        monkeypatch.setattr(f'{modpath}.get_embedding_service', lambda: fake)
    return fake


@pytest.fixture
def knowledge(app_context):
    """One user and company with one item of each source type. Returns a dict of ids."""
    user = _make_user()
    company = _make_company(user.id)
    note = JournalEntry(user_id=user.id, company_id=company.id, entry_type='observation',
                        title='Moat note', content='Switching costs keep customers.')
    decision = DecisionJournal(user_id=user.id, company_id=company.id, decision_type='buy',
                               decision_date=date(2026, 1, 5), investment_thesis='Durable moat at a fair price.')
    mistake = MistakeLog(user_id=user.id, company_id=company.id, title='Overpaid',
                         description='Bought above intrinsic value.', mistake_type='valuation',
                         lesson_learned='Anchor to a valuation range.')
    resource = CompanyResource(user_id=user.id, company_id=company.id, resource_type='link',
                               title='10-K', description='Annual report with segment data.')
    general = JournalEntry(user_id=user.id, company_id=None, entry_type='observation',
                           title='General note', content='A reflection not tied to a company.')
    db.session.add_all([note, decision, mistake, resource, general])
    db.session.commit()
    return {'user': user.id, 'company': company.id, 'note': note.id, 'decision': decision.id,
            'mistake': mistake.id, 'resource': resource.id, 'general': general.id}


def _chunks(user_id, **filters):
    return KnowledgeChunk.query.filter_by(user_id=user_id, **filters).all()


def test_blocknote_blocks_can_become_lines():
    content = json.dumps([
        {'type': 'paragraph', 'content': [{'type': 'text', 'text': 'First block.'}]},
        {'type': 'paragraph', 'content': []},
        {'type': 'paragraph', 'content': [{'type': 'text', 'text': 'Second'}, {'type': 'text', 'text': 'block.'}]},
    ])
    assert blocknote_to_text(content) == 'First block. Second block.'
    assert blocknote_to_text(content, block_separator='\n') == 'First block.\nSecond block.'


def test_plain_and_html_text_keep_lines():
    assert blocknote_to_text('Line one.\n\n  Line   two.', block_separator='\n') == 'Line one.\nLine two.'
    assert blocknote_to_text('<p>Para A.</p><p>Para <b>B</b>.</p>', block_separator='\n') == 'Para A.\nPara B.'
    assert blocknote_to_text('Line one.\nLine two.') == 'Line one. Line two.'


def test_indexes_every_source_type(knowledge, stub_embedding, llm_calls):
    run = index_user_knowledge(knowledge['user'])

    assert run.items_indexed == 5
    types = {c.source_type for c in _chunks(knowledge['user'])}
    assert types == {'journal', 'decision', 'mistake', 'resource'}
    for chunk in _chunks(knowledge['user']):
        assert chunk.context == LLM_CONTEXT
        assert chunk.context_method == 'llm'
        assert len(chunk.content_hash) == 64
        assert chunk.embedding_model == 'stub-embedding'
        assert chunk.chunk_index == 0
    general = _chunks(knowledge['user'], source_id=knowledge['general'])[0]
    assert general.company_id is None


def test_finding_indexed_as_journal_with_type_in_title(app_context, stub_embedding, llm_calls):
    user = _make_user()
    company = _make_company(user.id)
    flagged = add_finding(user.id, company.id, 'red_flag', 'High debt load.', signal='Leverage')
    plain = add_finding(user.id, company.id, 'must_exit', 'Founder leaves.')
    db.session.commit()

    index_user_knowledge(user.id)

    assert _chunks(user.id, source_type='finding') == []
    assert _chunks(user.id, source_type='journal', source_id=flagged.id)[0].title == 'Red Flag: Leverage'
    assert _chunks(user.id, source_type='journal', source_id=plain.id)[0].title == 'Must Exit'


def test_blocknote_content_indexed_as_text(app_context, stub_embedding, llm_calls):
    user = _make_user()
    entry = JournalEntry(user_id=user.id, entry_type='observation', title='Editor note', content=json.dumps([
        {'id': 'abc', 'type': 'paragraph', 'props': {'textColor': 'default'},
         'content': [{'type': 'text', 'text': 'Pricing power is real.', 'styles': {}}]},
    ]))
    db.session.add(entry)
    db.session.commit()

    index_user_knowledge(user.id)

    chunk = _chunks(user.id)[0]
    assert chunk.summary == 'Pricing power is real.'


def test_unchanged_rerun_makes_no_calls(knowledge, embed_calls, llm_calls):
    index_user_knowledge(knowledge['user'])
    llm_before, embed_before = len(llm_calls), len(embed_calls)
    work = []

    run = index_user_knowledge(knowledge['user'], on_work=work.append)

    assert (len(llm_calls), len(embed_calls)) == (llm_before, embed_before)
    assert work == []
    assert run.items_indexed == 0


def test_edit_without_text_change_makes_no_calls(knowledge, embed_calls, llm_calls):
    index_user_knowledge(knowledge['user'])
    llm_before, embed_before = len(llm_calls), len(embed_calls)
    note = db.session.get(JournalEntry, knowledge['note'])
    note.sentiment = 'bullish'
    note.updated_at = now_utc().replace(tzinfo=None) + timedelta(minutes=5)
    db.session.commit()

    index_user_knowledge(knowledge['user'])

    assert (len(llm_calls), len(embed_calls)) == (llm_before, embed_before)


def test_edit_during_run_indexed_next_run(knowledge, stub_embedding, monkeypatch):
    start = datetime(2026, 10, 30, 2, 0, 0)
    monkeypatch.setattr(knowledge_index, 'now_utc', lambda: start)
    edited = []

    def edit_during_run(prompt, **kwargs):
        if not edited:
            note = db.session.get(JournalEntry, knowledge['note'])
            note.content = 'Switching costs fell after the price war.'
            note.updated_at = start + timedelta(seconds=1)
            edited.append(True)
        return LLM_CONTEXT

    monkeypatch.setattr(knowledge_context.ai_service, 'generate_text', edit_during_run)
    index_user_knowledge(knowledge['user'])
    assert db.session.get(User, knowledge['user']).knowledge_indexed_at == start

    index_user_knowledge(knowledge['user'])

    chunk = _chunks(knowledge['user'], source_type='journal', source_id=knowledge['note'])[0]
    assert chunk.summary == 'Switching costs fell after the price war.'


def test_shorter_note_leaves_no_old_pieces(app_context, stub_embedding, llm_calls):
    user = _make_user()
    entry = JournalEntry(user_id=user.id, entry_type='observation', title='Long', content=_sentences(60))
    db.session.add(entry)
    db.session.commit()
    index_user_knowledge(user.id)
    assert len(_chunks(user.id)) >= 3

    entry.content = 'Now it is short.'
    db.session.commit()
    index_user_knowledge(user.id)

    assert [(c.chunk_index, c.summary) for c in _chunks(user.id)] == [(0, 'Now it is short.')]


def test_deleted_sources_disappear_from_search(knowledge, stub_embedding, llm_calls):
    index_user_knowledge(knowledge['user'])
    for model, key in ((JournalEntry, 'note'), (CompanyResource, 'resource'), (MistakeLog, 'mistake')):
        db.session.delete(db.session.get(model, knowledge[key]))
    db.session.commit()

    run = index_user_knowledge(knowledge['user'])

    assert run.chunks_removed == 3
    remaining = {(c.source_type, c.source_id) for c in _chunks(knowledge['user'])}
    assert remaining == {('decision', knowledge['decision']), ('journal', knowledge['general'])}
    found = {(r['source_type'], r['source_id']) for r in search_my_knowledge(knowledge['user'], 'moat', total_cap=20)}
    assert found <= remaining


def test_old_finding_chunks_removed(knowledge, stub_embedding, llm_calls):
    _make_chunk(knowledge['user'], knowledge['company'], 'finding', 1000, 'A legacy finding.')
    db.session.commit()

    index_user_knowledge(knowledge['user'])

    assert _chunks(knowledge['user'], source_type='finding') == []


def test_fact_buried_in_long_note_is_found(app_context, keyword_embedding, llm_calls):
    user = _make_user()
    company = _make_company(user.id)
    content = (_sentences(30, 'a') + '\n' + _sentences(30, 'b') + '\n' + _sentences(10, 'c')
               + ' Gross margin of 61.3% came from the service business. ' + _sentences(10, 'd'))
    db.session.add(JournalEntry(user_id=user.id, company_id=company.id, entry_type='observation',
                                title='Annual review', content=content))
    db.session.commit()

    index_user_knowledge(user.id)
    assert len(_chunks(user.id)) >= 3

    top = search_my_knowledge(user.id, '61.3% gross margin', total_cap=1)[0]
    assert '61.3%' in top['summary']


def test_no_consent_removes_chunks_and_calls_nothing(knowledge, embed_calls, llm_calls):
    index_user_knowledge(knowledge['user'])
    user = db.session.get(User, knowledge['user'])
    user.ai_consent_given = False
    db.session.commit()
    llm_before, embed_before = len(llm_calls), len(embed_calls)

    run = index_user_knowledge(knowledge['user'])

    assert run.consent is False
    assert _chunks(knowledge['user']) == []
    assert (len(llm_calls), len(embed_calls)) == (llm_before, embed_before)


def test_no_consent_creates_no_chunks(knowledge, embed_calls, llm_calls):
    user = db.session.get(User, knowledge['user'])
    user.ai_consent_given = False
    db.session.commit()

    index_user_knowledge(knowledge['user'])

    assert _chunks(knowledge['user']) == []
    assert (llm_calls, embed_calls) == ([], [])


def test_llm_failure_marks_prefix(knowledge, stub_embedding, llm_down):
    index_user_knowledge(knowledge['user'])

    note = _chunks(knowledge['user'], source_type='journal', source_id=knowledge['note'])[0]
    assert note.context_method == 'prefix'
    assert note.context == 'ASML Holding — Moat note:'
    assert {c.context_method for c in _chunks(knowledge['user'])} == {'prefix'}


def test_no_budget_marks_prefix(knowledge, stub_embedding, llm_calls):
    user = db.session.get(User, knowledge['user'])
    user.ai_tokens_used = user.ai_tokens_limit
    db.session.commit()

    index_user_knowledge(knowledge['user'])

    assert llm_calls == []
    assert {c.context_method for c in _chunks(knowledge['user'])} == {'prefix'}


def test_llm_tokens_counted_against_budget(knowledge, stub_embedding, llm_calls):
    index_user_knowledge(knowledge['user'])
    assert db.session.get(User, knowledge['user']).ai_tokens_used > 0


def test_opt_out_downgrades_to_prefix(knowledge, stub_embedding, llm_calls):
    index_user_knowledge(knowledge['user'])
    user = db.session.get(User, knowledge['user'])
    user.knowledge_context_enabled = False
    db.session.commit()
    llm_before = len(llm_calls)

    index_user_knowledge(knowledge['user'])

    assert len(llm_calls) == llm_before
    assert {c.context_method for c in _chunks(knowledge['user'])} == {'prefix'}


def test_prefix_rows_upgraded_when_llm_available(knowledge, stub_embedding, monkeypatch):
    answers = {'up': False}

    def flaky(prompt, **kwargs):
        if not answers['up']:
            raise RuntimeError('provider unreachable')
        return LLM_CONTEXT

    monkeypatch.setattr(knowledge_context.ai_service, 'generate_text', flaky)
    index_user_knowledge(knowledge['user'])
    assert {c.context_method for c in _chunks(knowledge['user'])} == {'prefix'}

    answers['up'] = True
    index_user_knowledge(knowledge['user'])

    assert {c.context_method for c in _chunks(knowledge['user'])} == {'llm'}


def test_embedding_model_change_reembeds(knowledge, stub_embedding, embed_calls, llm_calls):
    index_user_knowledge(knowledge['user'])
    stub_embedding.model_id = 'stub-embedding-v2'
    embed_before = len(embed_calls)

    index_user_knowledge(knowledge['user'])

    assert len(embed_calls) - embed_before == len(_chunks(knowledge['user']))
    assert {c.embedding_model for c in _chunks(knowledge['user'])} == {'stub-embedding-v2'}


def test_failed_embedding_retried_next_run(knowledge, stub_embedding, llm_calls, monkeypatch):
    original = stub_embedding.embed
    monkeypatch.setattr(stub_embedding, 'embed', lambda text, use_cache=True: None)
    index_user_knowledge(knowledge['user'])
    assert {c.embedding_model for c in _chunks(knowledge['user'])} == {None}

    monkeypatch.setattr(stub_embedding, 'embed', original)
    index_user_knowledge(knowledge['user'])

    assert {c.embedding_model for c in _chunks(knowledge['user'])} == {'stub-embedding'}


def test_no_embedding_provider_fails_without_deleting(knowledge, stub_embedding, llm_calls):
    index_user_knowledge(knowledge['user'])
    before = len(_chunks(knowledge['user']))
    watermark = db.session.get(User, knowledge['user']).knowledge_indexed_at
    db.session.delete(db.session.get(JournalEntry, knowledge['note']))
    db.session.commit()
    stub_embedding.model_id = None

    with pytest.raises(IndexUnavailable):
        index_user_knowledge(knowledge['user'])

    assert len(_chunks(knowledge['user'])) == before
    assert db.session.get(User, knowledge['user']).knowledge_indexed_at == watermark


def test_wrong_dimension_provider_is_unavailable(knowledge, stub_embedding, llm_calls):
    stub_embedding.dimension = 512

    with pytest.raises(IndexUnavailable):
        index_user_knowledge(knowledge['user'])

    assert _chunks(knowledge['user']) == []


def test_cap_holds_back_watermark(knowledge, stub_embedding, llm_calls, monkeypatch):
    monkeypatch.setattr(knowledge_index, 'MAX_ITEMS_PER_RUN', 2)

    run = index_user_knowledge(knowledge['user'])

    assert (run.items_indexed, run.remaining) == (2, 3)
    assert db.session.get(User, knowledge['user']).knowledge_indexed_at is None

    index_user_knowledge(knowledge['user'])
    run = index_user_knowledge(knowledge['user'])

    assert run.remaining == 0
    assert len({(c.source_type, c.source_id) for c in _chunks(knowledge['user'])}) == 5
    assert db.session.get(User, knowledge['user']).knowledge_indexed_at is not None


def test_on_work_called_once_with_item_count(knowledge, stub_embedding, llm_calls):
    work = []
    index_user_knowledge(knowledge['user'], on_work=work.append)
    assert work == [5]


def test_other_users_chunks_untouched(knowledge, stub_embedding, llm_calls):
    other = _make_user('other@example.com')
    _make_chunk(other.id, None, 'journal', 99999, 'Someone else entirely.')
    db.session.commit()

    index_user_knowledge(knowledge['user'])

    assert len(_chunks(other.id)) == 1
