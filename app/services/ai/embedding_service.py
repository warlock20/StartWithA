# Investment Checklist Platform
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
Embedding Service - Unified entry point for all embedding operations

Follows the same pattern as ai_service.py for consistency.
Routes embedding requests to optimal providers based on
availability and configuration.

Usage:
    from app.services.ai.embedding_service import embedding_service
    
    # Simple embedding
    vector = embedding_service.embed("My investment thesis...")
    
    # Batch embedding
    vectors = embedding_service.embed_batch(["Text 1", "Text 2"])
    
    # Similarity search
    similar = embedding_service.find_similar(query_vector, candidates)
    
    # Convenience functions
    from app.services.ai.embedding_service import embed, embed_batch
    vector = embed("Hello world")
"""

import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import numpy as np

from .providers.embeddings import (
    BaseEmbeddingProvider,
    get_local_provider,
    OpenAIEmbeddingProvider,
    GeminiEmbeddingProvider,
    VoyageEmbeddingProvider,
    CohereEmbeddingProvider,
    TfidfEmbeddingProvider,
)

from .config import (
    get_ai_config,
    EmbeddingProvider,
    DEFAULT_EMBEDDING_PRIORITY,
)

logger = logging.getLogger(__name__)


# Provider class mapping (LOCAL is lazy to avoid importing PyTorch at startup)
PROVIDER_CLASSES = {
    EmbeddingProvider.LOCAL: get_local_provider,
    EmbeddingProvider.OPENAI: OpenAIEmbeddingProvider,
    EmbeddingProvider.GEMINI: GeminiEmbeddingProvider,
    EmbeddingProvider.VOYAGE: VoyageEmbeddingProvider,
    EmbeddingProvider.COHERE: CohereEmbeddingProvider,
    EmbeddingProvider.TFIDF: TfidfEmbeddingProvider,
}

class EmbeddingService:
    """
    Unified embedding service that routes to optimal providers.
    
    This service:
    - Manages embedding provider instances
    - Routes to best available provider
    - Provides caching for embeddings
    - Handles fallbacks when preferred provider unavailable
    """
    
    def __init__(
        self,
        preferred_provider: Optional[EmbeddingProvider] = None,
        provider_priority: Optional[List[EmbeddingProvider]] = None,
        cache_dir: Optional[str] = None,
        enable_cache: bool = True
    ):
        """
        Initialize embedding service.
        
        Args:
            preferred_provider: Force use of specific provider
            provider_priority: Custom priority order for fallback
            cache_dir: Directory for caching embeddings
            enable_cache: Whether to cache embeddings
        """
        config = get_ai_config()
        self._provider_priority = provider_priority or DEFAULT_EMBEDDING_PRIORITY
        self._enable_cache = enable_cache if enable_cache is not None else config.embedding_cache_enabled
        self._cache_dir = Path(cache_dir) if cache_dir else Path(config.embedding_cache_dir)
        self._providers: Dict[EmbeddingProvider, BaseEmbeddingProvider] = {}
        self._active_provider: Optional[EmbeddingProvider] = None
        
        # Setup cache
        self._cache_dir = Path(cache_dir) if cache_dir else Path('instance/embedding_cache')
        if self._enable_cache:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize providers
        self._initialize_providers()
        
        # Select active provider
        if preferred_provider:
            self._select_provider(preferred_provider)
        else:
            self._select_best_provider()
    
    def _initialize_providers(self):
        """Initialize all available providers"""
        for provider_type in self._provider_priority:
            try:
                provider_class_or_factory = PROVIDER_CLASSES[provider_type]
                # LOCAL uses a factory function that returns the class (lazy import)
                if callable(provider_class_or_factory) and provider_type == EmbeddingProvider.LOCAL:
                    provider_class = provider_class_or_factory()
                else:
                    provider_class = provider_class_or_factory
                provider = provider_class()

                if provider.is_available():
                    self._providers[provider_type] = provider
                    logger.debug(f"Embedding provider available: {provider_type.value}")
            except Exception as e:
                logger.debug(f"Could not initialize {provider_type.value}: {e}")
        
        if not self._providers:
            logger.warning("No embedding providers available!")
    
    def _select_provider(self, provider_type: EmbeddingProvider):
        """Select a specific provider"""
        if provider_type in self._providers:
            self._active_provider = provider_type
            logger.info(f"Embedding service using: {provider_type.value}")
        else:
            logger.warning(f"Requested provider {provider_type.value} not available, selecting best")
            self._select_best_provider()
    
    def _select_best_provider(self):
        """Select the best available provider based on priority"""
        for provider_type in self._provider_priority:
            if provider_type in self._providers:
                self._active_provider = provider_type
                logger.info(f"Embedding service using: {provider_type.value}")
                return
        
        logger.error("No embedding providers available!")
    
    @property
    def provider(self) -> Optional[str]:
        """Current active provider name"""
        return self._active_provider.value if self._active_provider else None
    
    @property
    def dimension(self) -> int:
        """Embedding dimension for active provider"""
        if self._active_provider and self._active_provider in self._providers:
            return self._providers[self._active_provider].dimension
        return 0
    
    def _get_provider(self) -> Optional[BaseEmbeddingProvider]:
        """Get the active provider instance"""
        if self._active_provider:
            return self._providers.get(self._active_provider)
        return None
    
    # ============================================================
    # Core Embedding Methods
    # ============================================================
    
    def embed(self, text: str, use_cache: bool = True) -> Optional[np.ndarray]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            use_cache: Whether to use cache
            
        Returns:
            Embedding vector as numpy array
        """
        if not text or not text.strip():
            return None
        
        text = text.strip()[:8000]  # Limit length
        
        # Check cache
        if use_cache and self._enable_cache:
            cached = self._get_cached(text)
            if cached is not None:
                return cached
        
        # Generate embedding
        provider = self._get_provider()
        if not provider:
            return None
        
        embedding = provider.embed(text)
        
        # Cache result
        if embedding is not None and use_cache and self._enable_cache:
            self._set_cached(text, embedding)
        
        return embedding
    
    def embed_batch(
        self,
        texts: List[str],
        use_cache: bool = True
    ) -> List[Optional[np.ndarray]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            use_cache: Whether to use cache
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        provider = self._get_provider()
        if not provider:
            return [None] * len(texts)
        
        if use_cache and self._enable_cache:
            # Check cache for each text
            results = [None] * len(texts)
            uncached_indices = []
            uncached_texts = []
            
            for i, text in enumerate(texts):
                if text and text.strip():
                    cached = self._get_cached(text.strip()[:8000])
                    if cached is not None:
                        results[i] = cached
                    else:
                        uncached_indices.append(i)
                        uncached_texts.append(text.strip()[:8000])
            
            # Embed uncached texts
            if uncached_texts:
                new_embeddings = provider.embed_batch(uncached_texts)
                for i, idx in enumerate(uncached_indices):
                    if new_embeddings[i] is not None:
                        results[idx] = new_embeddings[i]
                        self._set_cached(uncached_texts[i], new_embeddings[i])
            
            return results
        else:
            # No caching
            return provider.embed_batch([t.strip()[:8000] if t else "" for t in texts])
    
    # ============================================================
    # Similarity Methods
    # ============================================================
    
    def compute_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray
    ) -> float:
        """
        Compute cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding
            embedding2: Second embedding
            
        Returns:
            Similarity score between -1 and 1
        """
        """Compute cosine similarity between two embeddings."""
        if embedding1 is None or embedding2 is None:
            return 0.0

        if len(embedding1) != len(embedding2):
            logger.warning(
                f"Embedding dimension mismatch: {len(embedding1)} vs {len(embedding2)}. "
                "This can happen when mixing providers. Returning 0.0"
            )
            return 0.0
        
        provider = self._get_provider()
        if provider:
            return provider.compute_similarity(embedding1, embedding2)
        return 0.0
    
    def find_similar(
        self,
        query_embedding: np.ndarray,
        candidates: List[Tuple[Any, np.ndarray]],
        top_k: int = 5,
        min_similarity: float = 0.5
    ) -> List[Tuple[Any, float]]:
        """
        Find most similar embeddings from candidates.
        
        Args:
            query_embedding: Query vector
            candidates: List of (id, embedding) tuples
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of (id, similarity) tuples, sorted desc
        """
        if query_embedding is None or not candidates:
            return []
        
        results = []
        for item_id, embedding in candidates:
            if embedding is not None:
                similarity = self.compute_similarity(query_embedding, embedding)
                if similarity >= min_similarity:
                    results.append((item_id, similarity))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def compute_text_similarity(self, text1: str, text2: str) -> float:
        """
        Compute similarity between two texts.
        
        Convenience method that handles embedding generation.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score
        """
        emb1 = self.embed(text1)
        emb2 = self.embed(text2)
        return self.compute_similarity(emb1, emb2)
    
    # ============================================================
    # Cache Methods
    # ============================================================
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text"""
        text_hash = hashlib.md5(text.encode()).hexdigest()
        return f"{self.provider}_{text_hash}"
    
    def _get_cached(self, text: str) -> Optional[np.ndarray]:
        """Get embedding from cache"""
        cache_key = self._get_cache_key(text)
        cache_file = self._cache_dir / f"{cache_key}.npy"
        
        if cache_file.exists():
            try:
                return np.load(cache_file)
            except Exception:
                pass
        return None
    
    def _set_cached(self, text: str, embedding: np.ndarray):
        """Save embedding to cache"""
        try:
            cache_key = self._get_cache_key(text)
            cache_file = self._cache_dir / f"{cache_key}.npy"
            np.save(cache_file, embedding)
        except Exception as e:
            logger.warning(f"Failed to cache embedding: {e}")
    
    def clear_cache(self):
        """Clear all cached embeddings"""
        if self._cache_dir.exists():
            for cache_file in self._cache_dir.glob("*.npy"):
                try:
                    cache_file.unlink()
                except Exception:
                    pass
    
    # ============================================================
    # Status Methods
    # ============================================================
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status information"""
        return {
            'active_provider': self.provider,
            'dimension': self.dimension,
            'available_providers': [p.value for p in self._providers.keys()],
            'cache_enabled': self._enable_cache,
            'cache_dir': str(self._cache_dir),
        }
    
    def get_available_providers(self) -> List[str]:
        """List all available providers"""
        return [p.value for p in self._providers.keys()]
    
    def is_available(self) -> bool:
        """Check if any provider is available"""
        return len(self._providers) > 0


# ============================================================
# Singleton Instance
# ============================================================

_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service(
    preferred_provider: Optional[str] = None,
    reset: bool = False
) -> EmbeddingService:
    """
    Get the singleton embedding service instance.
    
    Args:
        preferred_provider: Force specific provider
        reset: Force re-initialization
        
    Returns:
        EmbeddingService singleton
    """
    global _embedding_service
    
    if _embedding_service is None or reset:
        provider_enum = None
        if preferred_provider:
            try:
                provider_enum = EmbeddingProvider(preferred_provider)
            except ValueError:
                logger.warning(f"Unknown provider: {preferred_provider}")
        
        _embedding_service = EmbeddingService(preferred_provider=provider_enum)
    
    return _embedding_service


def reset_embedding_service():
    """Reset the embedding service singleton"""
    global _embedding_service
    _embedding_service = None


# ============================================================
# Convenience Functions
# ============================================================

def embed(text: str, use_cache: bool = True) -> Optional[np.ndarray]:
    """
    Quick access to single text embedding.
    
    Args:
        text: Text to embed
        use_cache: Whether to use cache
        
    Returns:
        Embedding vector
    """
    return get_embedding_service().embed(text, use_cache)


def embed_batch(texts: List[str], use_cache: bool = True) -> List[Optional[np.ndarray]]:
    """
    Quick access to batch text embedding.
    
    Args:
        texts: Texts to embed
        use_cache: Whether to use cache
        
    Returns:
        List of embedding vectors
    """
    return get_embedding_service().embed_batch(texts, use_cache)


def compute_similarity(text1: str, text2: str) -> float:
    """
    Quick access to text similarity.
    
    Args:
        text1: First text
        text2: Second text
        
    Returns:
        Similarity score
    """
    return get_embedding_service().compute_text_similarity(text1, text2)