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
Local Embedding Provider

Uses Sentence Transformers for local, offline embeddings.
No API key required, fast, and free.

Recommended models:
- all-MiniLM-L6-v2: Fast, good quality (384 dims)
- all-mpnet-base-v2: Better quality, slower (768 dims)
- multi-qa-MiniLM-L6-cos-v1: Optimized for semantic search (384 dims)
"""

import logging
from typing import List, Optional
import numpy as np

from .base import BaseEmbeddingProvider

# NOTE: SentenceTransformer is imported lazily in _load_model() to avoid
# loading PyTorch (~300MB) on every process startup. This is critical for
# memory on Railway where each Gunicorn/Celery worker would otherwise
# import torch at startup even when embeddings are never used.

logger = logging.getLogger(__name__)


class LocalEmbeddingProvider(BaseEmbeddingProvider):
    """
    Local embeddings using Sentence Transformers.
    
    Advantages:
    - No API costs
    - Fast inference
    - Works offline
    - Privacy (data never leaves your server)
    """
    
    # Available models with their dimensions
    MODELS = {
        'all-MiniLM-L6-v2': 384,           # Fast, good quality
        'all-mpnet-base-v2': 768,           # Better quality
        'BAAI/bge-base-en-v1.5': 768,       # MTEB benchmark leader, better for domain text
        'multi-qa-MiniLM-L6-cos-v1': 384,   # Optimized for search
        'paraphrase-MiniLM-L6-v2': 384,     # Good for paraphrase detection
    }

    DEFAULT_MODEL = 'BAAI/bge-base-en-v1.5'
    
    def __init__(self, model: str = None, dimension: int = None):
        model = model or self.DEFAULT_MODEL
        dimension = dimension or self.MODELS.get(model, 384)
        super().__init__(model, dimension)
        self._model_instance = None
    
    def _load_model(self):
        """Lazy load the model (imports torch + sentence-transformers on first use only)"""
        if self._model_instance is None:
            from sentence_transformers import SentenceTransformer
            self._model_instance = SentenceTransformer(self.model)
            logger.info(f"Loaded local embedding model: {self.model}")
    
    def is_available(self) -> bool:
        """Check if sentence-transformers is installed"""
        try:
            import sentence_transformers  # noqa: F401
            return True
        except ImportError:
            return False
    
    def embed(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding for single text"""
        if not text or not text.strip():
            return None
        
        try:
            self._load_model()
            embedding = self._model_instance.encode(
                text.strip()[:8000],  # Limit length
                convert_to_numpy=True,
                normalize_embeddings=True  # L2 normalize for cosine similarity
            )
            return embedding.astype(np.float32)
        except Exception as e:
            logger.error(f"Local embedding failed: {e}")
            return None
    
    def embed_batch(self, texts: List[str]) -> List[Optional[np.ndarray]]:
        """
        Batch embedding - more efficient than individual calls.
        """
        if not texts:
            return []
        
        try:
            self._load_model()
            
            # Filter and track valid texts
            valid_indices = []
            valid_texts = []
            for i, text in enumerate(texts):
                if text and text.strip():
                    valid_indices.append(i)
                    valid_texts.append(text.strip()[:8000])
            
            if not valid_texts:
                return [None] * len(texts)
            
            # Batch encode
            embeddings = self._model_instance.encode(
                valid_texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False
            )
            
            # Map back to original indices
            results = [None] * len(texts)
            for i, idx in enumerate(valid_indices):
                results[idx] = embeddings[i].astype(np.float32)
            
            return results
            
        except Exception as e:
            logger.error(f"Local batch embedding failed: {e}")
            return [None] * len(texts)