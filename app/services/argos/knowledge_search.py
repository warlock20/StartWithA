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

`search_my_knowledge` embeds the query, cosine-ranks the user's KnowledgeChunks,
and fills the result under a HARD budget: a total ceiling AND per-source caps, so
unbounded sources (notes, links) can never crowd out research findings. Chunks
from currently-held companies get a small ranking bonus (the portfolio reflects
where the user's real knowledge concentrates).

Only summaries are returned here. Raw note/resource text is fetched separately via
`get_resource`, and only for the owning user.
"""

import numpy as np

from app.models.knowledge_chunk import KnowledgeChunk
from app.models.portfolio import PortfolioPosition
from app.models.journal import JournalEntry
from app.models.company import CompanyResource
from app.services.ai.embedding_service import get_embedding_service

_DEFAULT_CAPS = {'finding': 3, 'journal': 3, 'resource': 2, 'decision': 3, 'mistake': 2}
_HELD_BONUS = 0.05


def _held_company_ids(user_id):
    return {
        p.company_id
        for p in PortfolioPosition.query.filter_by(user_id=user_id, is_active=True).all()
    }


def search_my_knowledge(user_id, query, company_id=None, total_cap=8, per_source_caps=None):
    """
    Retrieve the user's knowledge for a query, under a total + per-source budget.

    Returns a list of dicts: {source_type, source_id, title, summary, score},
    at most `total_cap` items, with each source capped by `per_source_caps`.
    """
    caps = per_source_caps or dict(_DEFAULT_CAPS)

    query_vec = get_embedding_service().embed(query)
    if query_vec is None:
        return []
    query_vec = np.asarray(query_vec, dtype=np.float64)
    query_norm = np.linalg.norm(query_vec) or 1.0

    rows = KnowledgeChunk.query.filter_by(user_id=user_id)
    if company_id is not None:
        rows = rows.filter_by(company_id=company_id)

    held = _held_company_ids(user_id)

    scored = []
    for row in rows.all():
        if row.embedding is None:
            continue
        vec = np.asarray(row.embedding, dtype=np.float64)
        denom = query_norm * (np.linalg.norm(vec) or 1.0)
        score = float(np.dot(query_vec, vec) / denom)
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
