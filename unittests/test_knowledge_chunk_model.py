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
from app.models.user import User
from app.services.ai.config import EmbeddingProvider
from app.services.ai.embedding_service import EmbeddingService
from app.services.ai.providers.embeddings.tfidf import TfidfEmbeddingProvider


def test_knowledge_chunk_fields():
    for f in ['user_id', 'company_id', 'source_type', 'source_id',
              'title', 'summary', 'embedding', 'token_estimate', 'updated_at',
              'chunk_index', 'context', 'context_method', 'content_hash', 'embedding_model']:
        assert hasattr(KnowledgeChunk, f), f"missing {f}"


def test_user_has_knowledge_fields():
    for f in ['knowledge_context_enabled', 'knowledge_indexed_at']:
        assert hasattr(User, f), f"missing {f}"


def test_unique_key_is_per_piece():
    constraints = {c.name: c for c in KnowledgeChunk.__table__.constraints}
    assert 'uq_knowledge_source' not in constraints
    columns = [col.name for col in constraints['uq_knowledge_source_piece'].columns]
    assert columns == ['source_type', 'source_id', 'chunk_index']


def test_knowledge_chunk_exported_from_models_package():
    assert hasattr(models, 'KnowledgeChunk'), "KnowledgeChunk not registered in app.models"


def test_embedding_service_names_its_model():
    service = EmbeddingService(provider_priority=[EmbeddingProvider.TFIDF], enable_cache=False)
    assert service.model_id == 'tfidf/tfidf'


def test_embedding_service_without_provider_has_no_model(monkeypatch):
    monkeypatch.setattr(TfidfEmbeddingProvider, 'is_available', lambda self: False)
    service = EmbeddingService(provider_priority=[EmbeddingProvider.TFIDF], enable_cache=False)
    assert service.model_id is None


if __name__ == '__main__':
    test_knowledge_chunk_fields()
    test_knowledge_chunk_exported_from_models_package()
    print("PASS")
