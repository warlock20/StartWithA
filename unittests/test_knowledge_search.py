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

"""Budgeted knowledge retrieval: caps, ceiling, ownership (Task 8). DB-backed."""

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.argos.knowledge_search import search_my_knowledge, get_resource


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
