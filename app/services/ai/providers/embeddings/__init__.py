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
Embedding Providers Package

Available providers:
- LocalEmbeddingProvider: Sentence Transformers (offline, free)
- OpenAIEmbeddingProvider: OpenAI API
- GeminiEmbeddingProvider: Google Gemini API
- VoyageEmbeddingProvider: Voyage AI (Anthropic recommended)
- CohereEmbeddingProvider: Cohere API
- TfidfEmbeddingProvider: Fallback (always works)

Usage:
    from app.services.ai.providers.embeddings import (
        LocalEmbeddingProvider,
        OpenAIEmbeddingProvider,
        GeminiEmbeddingProvider,
    )
    
    provider = LocalEmbeddingProvider()
    if provider.is_available():
        embedding = provider.embed("My text...")
"""

from .base import BaseEmbeddingProvider
from .openai_embed import OpenAIEmbeddingProvider
from .gemini_embed import GeminiEmbeddingProvider
from .voyage import VoyageEmbeddingProvider
from .cohere import CohereEmbeddingProvider
from .tfidf import TfidfEmbeddingProvider


def get_local_provider():
    """Import LocalEmbeddingProvider on demand to avoid loading PyTorch at startup."""
    from .local import LocalEmbeddingProvider
    return LocalEmbeddingProvider


__all__ = [
    'BaseEmbeddingProvider',
    'get_local_provider',
    'OpenAIEmbeddingProvider',
    'GeminiEmbeddingProvider',
    'VoyageEmbeddingProvider',
    'CohereEmbeddingProvider',
    'TfidfEmbeddingProvider',
]