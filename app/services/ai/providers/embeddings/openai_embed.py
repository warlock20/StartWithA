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
OpenAI Embedding Provider

Uses OpenAI's embedding API.
High quality embeddings, requires API key.

Models:
- text-embedding-3-small: Good balance of quality/cost (1536 dims)
- text-embedding-3-large: Highest quality (3072 dims)
- text-embedding-ada-002: Legacy model (1536 dims)
"""

import logging
import os
from typing import List, Optional
import numpy as np

from .base import BaseEmbeddingProvider

logger = logging.getLogger(__name__)


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """
    OpenAI embeddings via API.
    
    Requires OPENAI_API_KEY environment variable.
    """
    
    MODELS = {
        'text-embedding-3-small': 1536,
        'text-embedding-3-large': 3072,
        'text-embedding-ada-002': 1536,
    }
    
    DEFAULT_MODEL = 'text-embedding-3-small'
    
    def __init__(self, model: str = None, dimension: int = None):
        model = model or self.DEFAULT_MODEL
        dimension = dimension or self.MODELS.get(model, 1536)
        super().__init__(model, dimension)
        self._client = None
    
    def _get_client(self):
        """Lazy initialize OpenAI client"""
        if self._client is None:
            import openai
            api_key = os.environ.get('OPENAI_API_KEY')
            self._client = openai.OpenAI(api_key=api_key)
        return self._client
    
    def is_available(self) -> bool:
        """Check if OpenAI is available"""
        try:
            import openai
            return bool(os.environ.get('OPENAI_API_KEY'))
        except ImportError:
            return False
    
    def embed(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding for single text"""
        if not text or not text.strip():
            return None
        
        try:
            client = self._get_client()
            response = client.embeddings.create(
                model=self.model,
                input=text.strip()[:8000]
            )
            return np.array(response.data[0].embedding, dtype=np.float32)
        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}")
            return None
    
    def embed_batch(self, texts: List[str]) -> List[Optional[np.ndarray]]:
        """Batch embedding - OpenAI supports batch API"""
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
            
            # Batch request (OpenAI supports up to 2048 inputs)
            response = client.embeddings.create(
                model=self.model,
                input=valid_texts[:2048]
            )
            
            # Map back to original indices
            results = [None] * len(texts)
            for i, idx in enumerate(valid_indices[:2048]):
                results[idx] = np.array(response.data[i].embedding, dtype=np.float32)
            
            return results
            
        except Exception as e:
            logger.error(f"OpenAI batch embedding failed: {e}")
            return [None] * len(texts)