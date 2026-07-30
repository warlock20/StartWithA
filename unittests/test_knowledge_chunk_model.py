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

"""KnowledgeChunk model shape (Task 6). Import-only, no DB required."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import app.models as models
from app.models.knowledge_chunk import KnowledgeChunk


def test_knowledge_chunk_fields():
    for f in ['user_id', 'company_id', 'source_type', 'source_id',
              'title', 'summary', 'embedding', 'token_estimate', 'updated_at']:
        assert hasattr(KnowledgeChunk, f), f"missing {f}"


def test_knowledge_chunk_exported_from_models_package():
    assert hasattr(models, 'KnowledgeChunk'), "KnowledgeChunk not registered in app.models"


if __name__ == '__main__':
    test_knowledge_chunk_fields()
    test_knowledge_chunk_exported_from_models_package()
    print("PASS")
