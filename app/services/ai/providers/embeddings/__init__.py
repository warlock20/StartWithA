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
from .local import LocalEmbeddingProvider
from .openai_embed import OpenAIEmbeddingProvider
from .gemini_embed import GeminiEmbeddingProvider
from .voyage import VoyageEmbeddingProvider
from .cohere import CohereEmbeddingProvider
from .tfidf import TfidfEmbeddingProvider

__all__ = [
    'BaseEmbeddingProvider',
    'LocalEmbeddingProvider',
    'OpenAIEmbeddingProvider',
    'GeminiEmbeddingProvider',
    'VoyageEmbeddingProvider',
    'CohereEmbeddingProvider',
    'TfidfEmbeddingProvider',
]