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

"""Budgeted knowledge retrieval: caps, ceiling, ownership, Postgres ranking (#393). DB-backed."""

import math
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
import pytest
from sqlalchemy import event, text

from app import db
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.portfolio import PortfolioPosition
from app.services.argos import knowledge_search
from app.services.argos.knowledge_search import search_my_knowledge, get_resource
from conftest import _make_company, _make_user

AXIS_MODEL = 'axis-embedding'


def test_respects_total_and_per_source_caps(app_context, seed_many_chunks, stub_embedding):
    uid = seed_many_chunks  # many findings + journal + resources for one user
    out = search_my_knowledge(
        uid, "moat competitive advantage", total_cap=8,
        per_source_caps={'finding': 3, 'journal': 3, 'resource': 2, 'decision': 3})

    assert len(out) <= 8, "total ceiling must hold"
    counts = Counter(o['source_type'] for o in out)
    assert counts['finding'] <= 3
    assert counts['journal'] <= 3
    assert counts['resource'] <= 2


def test_search_only_returns_own_chunks(app_context, seed_many_chunks, other_user, stub_embedding):
    # other_user has no chunks of their own → empty result, never the seeded user's.
    out = search_my_knowledge(other_user, "moat", total_cap=8)
    assert out == []


def test_get_resource_denies_other_user(app_context, seed_journal_resource, other_user):
    owner_id, journal_id = seed_journal_resource
    assert get_resource(owner_id, 'journal', journal_id) is not None
    assert get_resource(other_user, 'journal', journal_id) is None


# =========================================================================
# Ranking in Postgres (#393)
# =========================================================================

def _unit(similarity):
    """A 768-dim unit vector whose cosine similarity to the x-axis is `similarity`."""
    vec = np.zeros(768)
    vec[0] = similarity
    vec[1] = math.sqrt(1 - similarity ** 2)
    return vec


@pytest.fixture
def axis_embedding(monkeypatch):
    """Every query embeds to the x-axis, so a chunk's score is its `_unit` similarity."""
    class _AxisEmbeddingService:
        model_id = AXIS_MODEL
        dimension = 768
        calls = 0

        def embed(self, text, use_cache=True):
            self.calls += 1
            return _unit(1.0)

    fake = _AxisEmbeddingService()
    monkeypatch.setattr('app.services.argos.knowledge_search.get_embedding_service', lambda: fake)
    return fake


def _chunk(user_id, similarity, source_id, company_id=None, source_type='journal', model=AXIS_MODEL):
    db.session.add(KnowledgeChunk(
        user_id=user_id, company_id=company_id, source_type=source_type, source_id=source_id,
        title=f'{source_type} {source_id}', summary=f'piece {source_id}',
        embedding=_unit(similarity).tolist(), embedding_model=model, token_estimate=1))


_BIG_CAPS = {'decision': 100, 'journal': 100, 'resource': 100, 'mistake': 100}


def _numpy_reference(user_id, query_vec):
    """Today's ranking before #393: numpy cosine over every chunk, no bonus (nothing held)."""
    scored = []
    for row in KnowledgeChunk.query.filter_by(user_id=user_id).all():
        vec = np.asarray(row.embedding, dtype=np.float64)
        score = float(np.dot(query_vec, vec) / (np.linalg.norm(query_vec) * np.linalg.norm(vec)))
        scored.append((score, row.source_type, row.source_id))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored


def test_postgres_ranking_matches_numpy_cosine(app_context, seed_many_chunks, stub_embedding):
    uid = seed_many_chunks
    query = "moat competitive advantage"
    expected = _numpy_reference(uid, stub_embedding.embed(query))

    out = search_my_knowledge(uid, query, total_cap=30, per_source_caps=_BIG_CAPS)

    # Compared tie-aware: seed_many_chunks seeds vectors with hash(), which is
    # randomized per process, so some runs give two chunks the same vector, and
    # Postgres and numpy may order those exact ties differently.
    reference = {(t, i): score for score, t, i in expected}
    assert {(o['source_type'], o['source_id']) for o in out} == set(reference)
    for got in out:
        assert got['score'] == pytest.approx(reference[(got['source_type'], got['source_id'])],
                                             abs=1e-4)
    scores = [o['score'] for o in out]
    assert scores == sorted(scores, reverse=True)


def test_chunks_from_other_embedding_models_are_ignored(app_context, axis_embedding):
    user = _make_user()
    _chunk(user.id, 0.5, 1)
    _chunk(user.id, 1.0, 2, model='old-model')  # identical direction, different model
    _chunk(user.id, 1.0, 3, model=None)
    db.session.commit()

    out = search_my_knowledge(user.id, 'anything', per_source_caps=_BIG_CAPS)

    assert [o['source_id'] for o in out] == [1]
    assert out[0]['score'] == pytest.approx(0.5, abs=1e-4)


def test_company_filter_keeps_only_that_company(app_context, axis_embedding):
    user = _make_user()
    asml = _make_company(user.id)
    sap = _make_company(user.id, name='SAP SE', ticker='SAP')
    _chunk(user.id, 0.9, 1, company_id=asml.id)
    _chunk(user.id, 0.99, 2, company_id=sap.id)
    _chunk(user.id, 0.95, 3)
    db.session.commit()

    out = search_my_knowledge(user.id, 'anything', company_id=asml.id, per_source_caps=_BIG_CAPS)

    assert [o['source_id'] for o in out] == [1]


def test_held_company_bonus_reorders_candidates(app_context, axis_embedding):
    user = _make_user()
    held = _make_company(user.id)
    _chunk(user.id, 0.90, 1)
    _chunk(user.id, 0.88, 2, company_id=held.id)
    db.session.add(PortfolioPosition(user_id=user.id, company_id=held.id, is_active=True,
                                     total_shares=10, current_value=1000))
    db.session.commit()

    out = search_my_knowledge(user.id, 'anything', per_source_caps=_BIG_CAPS)

    assert [o['source_id'] for o in out] == [2, 1]
    assert out[0]['score'] == pytest.approx(0.88 + 0.05, abs=1e-4)


def test_only_the_nearest_candidates_per_source_are_considered(app_context, axis_embedding):
    user = _make_user()
    count = knowledge_search._CANDIDATE_LIMIT + 10
    for i in range(count):
        _chunk(user.id, 0.99 - i * 0.01, i)  # source_id 0 is nearest
    db.session.commit()

    out = search_my_knowledge(user.id, 'anything', total_cap=count, per_source_caps=_BIG_CAPS)

    assert [o['source_id'] for o in out] == list(range(knowledge_search._CANDIDATE_LIMIT))


def test_a_crowded_source_does_not_starve_the_others(app_context, axis_embedding):
    # 60 journal chunks, all nearer the query than the one mistake: a single
    # LIMIT 50 over all sources would hold only journals, and the journal cap
    # would leave 3 results with no mistake.
    user = _make_user()
    for i in range(knowledge_search._CANDIDATE_LIMIT + 10):
        _chunk(user.id, 0.99 - i * 0.01, i)  # 0.99 down to 0.40
    _chunk(user.id, 0.30, 500, source_type='mistake')
    db.session.commit()

    out = search_my_knowledge(user.id, 'anything')  # default caps: journal 3, mistake 2

    assert [(o['source_type'], o['source_id']) for o in out] == [
        ('journal', 0), ('journal', 1), ('journal', 2), ('mistake', 500)]


def test_no_embedding_model_means_no_search(app_context, axis_embedding, monkeypatch):
    user = _make_user()
    _chunk(user.id, 0.9, 1)
    db.session.commit()
    monkeypatch.setattr(axis_embedding, 'model_id', None)

    assert search_my_knowledge(user.id, 'anything') == []
    assert axis_embedding.calls == 0


# =========================================================================
# Cross-user search under a forced index (#393 scope note)
# =========================================================================
# An HNSW scan on pgvector < 0.8 returns about `hnsw.ef_search` (default 40)
# nearest vectors across ALL users and applies `WHERE user_id = ...` afterwards,
# so a user whose chunks aren't among the global nearest silently gets fewer
# rows. These tests set up exactly that case: another user owns many chunks
# close to the query, this user's chunks are far from it.

_OWN = 5
_CROWD = 200


def _spread(similarity, rng):
    """A unit vector at `similarity` to the x-axis, pointing in a random other direction."""
    other = rng.standard_normal(768)
    other[0] = 0.0
    other /= np.linalg.norm(other)
    vec = math.sqrt(1 - similarity ** 2) * other
    vec[0] = similarity
    return vec


@pytest.fixture
def crowded_by_other_user(app_context):
    """Returns (this user's id, other user's id); the other user crowds the query."""
    rng = np.random.default_rng(393)
    me = _make_user()
    crowd = _make_user(email='crowd@example.com')
    for i in range(_OWN):
        db.session.add(KnowledgeChunk(
            user_id=me.id, source_type='journal', source_id=i, summary=f'mine {i}',
            embedding=_spread(0.1, rng).tolist(), embedding_model=AXIS_MODEL))
    for i in range(_CROWD):
        db.session.add(KnowledgeChunk(
            user_id=crowd.id, source_type='journal', source_id=1000 + i, summary=f'crowd {i}',
            embedding=_spread(0.95, rng).tolist(), embedding_model=AXIS_MODEL))
    db.session.commit()
    return me.id, crowd.id


@pytest.fixture
def captured_sql():
    """Records (statement, params) of every knowledge_chunk SELECT on the session's engine."""
    seen = []

    def _record(conn, cursor, statement, params, context, executemany):
        if statement.lstrip().upper().startswith('SELECT') and 'FROM knowledge_chunk' in statement:
            seen.append((statement, params))

    event.listen(db.engine, 'before_cursor_execute', _record)
    yield seen
    event.remove(db.engine, 'before_cursor_execute', _record)


def _search_plan(statement, params):
    """EXPLAIN of a captured statement, in the current transaction (so SET LOCALs apply)."""
    rows = db.session.connection().exec_driver_sql('EXPLAIN ' + statement, params).all()
    return re.sub(r"'\[[^\]]*\]'", "'[...]'", '\n'.join(row[0] for row in rows))


def _own_ids(results):
    return sorted(r['source_id'] for r in results)


_PROBE_INDEX = 'ix_knowledge_chunk_embedding_hnsw_probe'

# What an HNSW-backed search would send per source: an ordered scan with LIMIT,
# which is the only shape an HNSW index can serve.
_PER_SOURCE_NEAREST = (
    'SELECT source_id FROM knowledge_chunk '
    'WHERE user_id = :uid AND embedding_model = :model AND source_type = :source '
    'ORDER BY embedding <=> CAST(:query AS vector) LIMIT :limit')


def _create_probe_index():
    """An HNSW index for this transaction only; the test's rollback drops it."""
    db.session.execute(text(
        f'CREATE INDEX {_PROBE_INDEX} ON knowledge_chunk USING hnsw (embedding vector_cosine_ops)'))


def _force_index_scans():
    """Push the planner off sequential scans and sorts, for this transaction only."""
    db.session.execute(text('ANALYZE knowledge_chunk'))
    # seqscan off alone still lets the planner use the user_id btree + a sort (exact),
    # so sort and bitmap scans go too; an HNSW index is then the cheapest ordered path.
    for setting in ('enable_seqscan', 'enable_sort', 'enable_bitmapscan'):
        db.session.execute(text(f'SET LOCAL {setting} = off'))


def test_cross_user_exact_scan_returns_all_own_chunks(crowded_by_other_user, axis_embedding,
                                                      captured_sql):
    # Even with an HNSW index present and forced, search's per-source window
    # (ordered by source_type, then distance) can't use it, so it stays exact.
    me, _ = crowded_by_other_user
    try:
        _create_probe_index()
        _force_index_scans()
        out = search_my_knowledge(me, 'anything', total_cap=20, per_source_caps=_BIG_CAPS)
        plan = _search_plan(*captured_sql[-1])
    finally:
        db.session.rollback()  # also drops the probe index (DDL is transactional)

    assert 'hnsw' not in plan.lower(), plan
    assert _own_ids(out) == list(range(_OWN))


def test_cross_user_with_forced_hnsw_index(crowded_by_other_user):
    """
    The scope note's gate for adding an HNSW index: with the index forced, a
    per-user nearest-chunks scan must still return all of this user's chunks.
    On pgvector 0.6.0 it returns none (the scan's ~40 candidates all belong to
    the other user), so there is no HNSW index and this test xfails. When it
    passes (pgvector >= 0.8 with `hnsw.iterative_scan`), HNSW can be added; the
    per-source window in `_nearest_chunks` would then need rewriting as one
    ordered scan per source (the shape probed here), since a window can't use it.
    """
    me, _ = crowded_by_other_user
    params = {'uid': me, 'model': AXIS_MODEL, 'source': 'journal',
              'query': str(_unit(1.0).tolist()), 'limit': knowledge_search._CANDIDATE_LIMIT}
    try:
        _create_probe_index()
        _force_index_scans()
        own = [row[0] for row in db.session.execute(text(_PER_SOURCE_NEAREST), params)]
        plan = '\n'.join(row[0] for row in db.session.execute(
            text('EXPLAIN ' + _PER_SOURCE_NEAREST), params))
        version = db.session.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")).scalar()
    finally:
        db.session.rollback()  # also drops the probe index (DDL is transactional)

    assert _PROBE_INDEX in plan, plan  # the index really ran
    if sorted(own) != list(range(_OWN)):
        pytest.xfail(f'HNSW post-filters by user on pgvector {version}: '
                     f'{len(own)} of {_OWN} own chunks returned')
