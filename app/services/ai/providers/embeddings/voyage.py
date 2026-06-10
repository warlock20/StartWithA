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
Voyage AI Embedding Provider

Anthropic's recommended embedding provider.
High quality embeddings optimized for retrieval.

Models:
- voyage-3: Latest, best quality (1024 dims)
- voyage-3-lite: Faster, smaller (512 dims)
- voyage-2: Previous generation (1024 dims)
- voyage-code-2: Optimized for code (1536 dims)
"""

import logging
import os
from typing import List, Optional
import numpy as np

from .base import BaseEmbeddingProvider

logger = logging.getLogger(__name__)


class VoyageEmbeddingProvider(BaseEmbeddingProvider):
    """
    Voyage AI embeddings via API.
    
    Recommended by Anthropic for use with Claude.
    Requires VOYAGE_API_KEY environment variable.
    """
    
    MODELS = {
        'voyage-3': 1024,
        'voyage-3-lite': 512,
        'voyage-2': 1024,
        'voyage-code-2': 1536,
    }
    
    DEFAULT_MODEL = 'voyage-2'
    
    def __init__(self, model: str = None, dimension: int = None):
        model = model or self.DEFAULT_MODEL
        dimension = dimension or self.MODELS.get(model, 1024)
        super().__init__(model, dimension)
        self._client = None
    
    def _get_client(self):
        """Lazy initialize Voyage client"""
        if self._client is None:
            import voyageai
            api_key = os.environ.get('VOYAGE_API_KEY')
            self._client = voyageai.Client(api_key=api_key)
        return self._client
    
    def is_available(self) -> bool:
        """Check if Voyage is available"""
        try:
            import voyageai
            return bool(os.environ.get('VOYAGE_API_KEY'))
        except ImportError:
            return False
    
    def embed(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding for single text"""
        if not text or not text.strip():
            return None
        
        try:
            client = self._get_client()
            result = client.embed(
                [text.strip()[:8000]],
                model=self.model
            )
            return np.array(result.embeddings[0], dtype=np.float32)
        except Exception as e:
            logger.error(f"Voyage embedding failed: {e}")
            return None
    
    def embed_batch(self, texts: List[str]) -> List[Optional[np.ndarray]]:
        """Batch embedding - Voyage supports batch API"""
        if not texts:
            return []
        
        try:
            client = self._get_client()
            
            # Filter valid texts
            valid_indices = []
            valid_texts = []
            for i, text in enumerate(texts):
                if text and text.strip():
                    valid_indices.append(i)
                    valid_texts.append(text.strip()[:8000])
            
            if not valid_texts:
                return [None] * len(texts)
            
            # Batch request (Voyage supports up to 128 texts)
            batch_size = 128
            all_embeddings = []
            
            for i in range(0, len(valid_texts), batch_size):
                batch = valid_texts[i:i + batch_size]
                result = client.embed(batch, model=self.model)
                all_embeddings.extend(result.embeddings)
            
            # Map back to original indices
            results = [None] * len(texts)
            for i, idx in enumerate(valid_indices):
                results[idx] = np.array(all_embeddings[i], dtype=np.float32)
            
            return results
            
        except Exception as e:
            logger.error(f"Voyage batch embedding failed: {e}")
            return [None] * len(texts)