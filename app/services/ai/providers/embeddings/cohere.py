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
Cohere Embedding Provider

Cohere's embedding API, good for search and retrieval.

Models:
- embed-english-v3.0: Best for English (1024 dims)
- embed-multilingual-v3.0: Multilingual (1024 dims)
- embed-english-light-v3.0: Faster, smaller (384 dims)
- embed-multilingual-light-v3.0: Multilingual light (384 dims)
"""

import logging
import os
from typing import List, Optional
import numpy as np

from .base import BaseEmbeddingProvider

logger = logging.getLogger(__name__)


class CohereEmbeddingProvider(BaseEmbeddingProvider):
    """
    Cohere embeddings via API.
    
    Requires COHERE_API_KEY environment variable.
    """
    
    MODELS = {
        'embed-english-v3.0': 1024,
        'embed-multilingual-v3.0': 1024,
        'embed-english-light-v3.0': 384,
        'embed-multilingual-light-v3.0': 384,
    }
    
    DEFAULT_MODEL = 'embed-english-v3.0'
    
    # Input types for Cohere
    INPUT_TYPES = {
        'search_document': 'For documents to be searched',
        'search_query': 'For search queries',
        'classification': 'For classification tasks',
        'clustering': 'For clustering tasks',
    }
    
    def __init__(
        self,
        model: str = None,
        dimension: int = None,
        input_type: str = 'search_document'
    ):
        model = model or self.DEFAULT_MODEL
        dimension = dimension or self.MODELS.get(model, 1024)
        super().__init__(model, dimension)
        self.input_type = input_type
        self._client = None
    
    def _get_client(self):
        """Lazy initialize Cohere client"""
        if self._client is None:
            import cohere
            api_key = os.environ.get('COHERE_API_KEY')
            self._client = cohere.Client(api_key)
        return self._client
    
    def is_available(self) -> bool:
        """Check if Cohere is available"""
        try:
            import cohere
            return bool(os.environ.get('COHERE_API_KEY'))
        except ImportError:
            return False
    
    def embed(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding for single text"""
        if not text or not text.strip():
            return None
        
        try:
            client = self._get_client()
            response = client.embed(
                texts=[text.strip()[:8000]],
                model=self.model,
                input_type=self.input_type
            )
            return np.array(response.embeddings[0], dtype=np.float32)
        except Exception as e:
            logger.error(f"Cohere embedding failed: {e}")
            return None
    
    def embed_batch(self, texts: List[str]) -> List[Optional[np.ndarray]]:
        """Batch embedding - Cohere supports batch API"""
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
            
            # Batch request (Cohere supports up to 96 texts)
            batch_size = 96
            all_embeddings = []
            
            for i in range(0, len(valid_texts), batch_size):
                batch = valid_texts[i:i + batch_size]
                response = client.embed(
                    texts=batch,
                    model=self.model,
                    input_type=self.input_type
                )
                all_embeddings.extend(response.embeddings)
            
            # Map back to original indices
            results = [None] * len(texts)
            for i, idx in enumerate(valid_indices):
                results[idx] = np.array(all_embeddings[i], dtype=np.float32)
            
            return results
            
        except Exception as e:
            logger.error(f"Cohere batch embedding failed: {e}")
            return [None] * len(texts)