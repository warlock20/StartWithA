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

"""
Budgeted knowledge retrieval — "the control".

`search_my_knowledge` embeds the query and has Postgres rank the user's
KnowledgeChunks by cosine distance (pgvector `<=>`), keeping only chunks made by
the current embedding model and the nearest `_CANDIDATE_LIMIT` of each source
type. From those it
fills the result under a HARD budget: a total ceiling AND per-source caps, so
unbounded sources (notes, links) can never crowd out research findings. Chunks
from currently-held companies get a small ranking bonus (the portfolio reflects
where the user's real knowledge concentrates).

The ranking is an exact scan of the user's rows (found through the user_id
index), with no vector index. An HNSW index would return about `hnsw.ef_search`
(default 40) nearest vectors across ALL users and filter by user afterwards, so
a user whose chunks aren't among the global nearest would silently get few or
none; on pgvector 0.6.0 they got none (`test_cross_user_with_forced_hnsw_index`).
Add HNSW once that test passes (pgvector >= 0.8 with `hnsw.iterative_scan`) and
per-user volume makes the exact scan slow.

Each result is one piece of an item plus its context (where the piece sits in its
item). Raw note/resource text is fetched separately via `get_resource`, and only
for the owning user.

Search embeds the query with the AI provider and the index holds the user's notes,
so it is off without the user's general AI consent.
"""

import math

import numpy as np
from sqlalchemy import func, select

from app import db
from app.models import User
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.portfolio import PortfolioPosition
from app.models.journal import JournalEntry
from app.models.company import CompanyResource
from app.services.ai.embedding_service import get_embedding_service

_DEFAULT_CAPS = {'journal': 3, 'resource': 2, 'decision': 3, 'mistake': 2}
_HELD_BONUS = 0.05
# Nearest chunks fetched from Postgres PER SOURCE; the bonus and caps then pick from these.
_CANDIDATE_LIMIT = 50

CONSENT_OFF_REASON = 'knowledge search is off: AI consent not given'


def _held_company_ids(user_id):
    return {
        p.company_id
        for p in PortfolioPosition.query.filter_by(user_id=user_id, is_active=True).all()
    }


def _nearest_chunks(user_id, model, query_vec, company_id=None):
    """
    The user's nearest chunks to `query_vec` per source, ranked in Postgres.

    Returns (chunk, cosine distance) pairs, nearest first: up to
    `_CANDIDATE_LIMIT` per source_type, so one source with many near chunks
    can't push the others out before the per-source caps run. Only vectors made
    by `model` are compared, since vectors from different models aren't
    comparable. This is an exact scan over the user's rows (see the module
    docstring for why there's no HNSW index).
    """
    vec = np.asarray(query_vec, dtype=np.float32)
    distance = KnowledgeChunk.embedding.cosine_distance(vec)
    rank = func.row_number().over(partition_by=KnowledgeChunk.source_type, order_by=distance)
    ranked = select(
        KnowledgeChunk.id, distance.label('distance'), rank.label('source_rank'),
    ).where(
        KnowledgeChunk.user_id == user_id,
        KnowledgeChunk.embedding_model == model,
        KnowledgeChunk.embedding.isnot(None),
    )
    if company_id is not None:
        ranked = ranked.where(KnowledgeChunk.company_id == company_id)
    ranked = ranked.subquery()

    return (
        db.session.query(KnowledgeChunk, ranked.c.distance)
        .join(ranked, KnowledgeChunk.id == ranked.c.id)
        .filter(ranked.c.source_rank <= _CANDIDATE_LIMIT)
        .order_by(ranked.c.distance)
        .all()
    )


def search_unavailable_reason(user_id):
    """Why knowledge search is off for this user, or None when it's on."""
    user = db.session.get(User, user_id)
    if user is None or not user.ai_consent_given:
        return CONSENT_OFF_REASON
    return None


def search_my_knowledge(user_id, query, company_id=None, total_cap=8, per_source_caps=None):
    """
    Retrieve the user's knowledge for a query, under a total + per-source budget.

    Returns a list of dicts: {source_type, source_id, title, summary, context, score},
    at most `total_cap` items, with each source capped by `per_source_caps`.
    `summary` is the piece's text. Empty, with no embedding call, when
    search_unavailable_reason gives a reason.
    """
    if search_unavailable_reason(user_id):
        return []
    caps = per_source_caps or dict(_DEFAULT_CAPS)

    embedder = get_embedding_service()
    model = embedder.model_id
    if model is None:
        return []
    query_vec = embedder.embed(query)
    if query_vec is None:
        return []

    held = _held_company_ids(user_id)

    scored = []
    for row, distance in _nearest_chunks(user_id, model, query_vec, company_id):
        if distance is None or math.isnan(distance):  # a zero vector has no direction
            continue
        score = 1.0 - float(distance)
        if row.company_id in held:
            score += _HELD_BONUS
        scored.append((score, row))

    scored.sort(key=lambda pair: pair[0], reverse=True)

    results = []
    used = {}
    for score, row in scored:
        if len(results) >= total_cap:
            break
        if used.get(row.source_type, 0) >= caps.get(row.source_type, 1):
            continue
        used[row.source_type] = used.get(row.source_type, 0) + 1
        results.append({
            'source_type': row.source_type,
            'source_id': row.source_id,
            'title': row.title,
            'summary': row.summary,
            'context': row.context,
            'score': round(score, 4),
        })
    return results


def get_resource(user_id, source_type, source_id):
    """Fetch raw content for one note/resource — only if owned by the user."""
    if source_type == 'journal':
        entry = JournalEntry.query.filter_by(id=source_id, user_id=user_id).first()
        return {'title': entry.title, 'content': entry.content} if entry else None
    if source_type == 'resource':
        resource = CompanyResource.query.filter_by(id=source_id, user_id=user_id).first()
        if not resource:
            return None
        return {'title': resource.title, 'url': resource.url,
                'description': resource.description}
    return None
