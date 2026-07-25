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

"""Knowledge index build + idempotency (Task 7). DB-backed (scratch Postgres)."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models.knowledge_chunk import KnowledgeChunk
from app.services.argos.knowledge_index import (
    index_company_knowledge, index_general_knowledge)


def test_index_creates_chunks_and_is_idempotent(app_context, seed_company_with_findings, stub_embedding):
    uid, cid = seed_company_with_findings

    n1 = index_company_knowledge(uid, cid)
    n2 = index_company_knowledge(uid, cid)

    assert n1 > 0, "expected at least one chunk from the seeded findings"
    assert n2 == n1, "re-indexing must upsert, not duplicate"
    assert KnowledgeChunk.query.filter_by(company_id=cid).count() == n1


def test_index_includes_company_mistakes(app_context, seed_portfolio_with_history, stub_embedding):
    uid, cid = seed_portfolio_with_history
    index_company_knowledge(uid, cid)

    assert KnowledgeChunk.query.filter_by(company_id=cid, source_type='mistake').count() == 1
    assert KnowledgeChunk.query.filter_by(company_id=cid, source_type='journal').count() == 1


def test_index_general_knowledge_covers_companyless_items(app_context, seed_general_knowledge, stub_embedding):
    uid = seed_general_knowledge
    n = index_general_knowledge(uid)

    assert n == 2  # one general note + one general mistake
    assert KnowledgeChunk.query.filter_by(
        user_id=uid, company_id=None, source_type='mistake').count() == 1
    assert KnowledgeChunk.query.filter_by(
        user_id=uid, company_id=None, source_type='journal').count() == 1
