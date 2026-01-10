"""
Gemini Embedding Provider

Uses Google's Gemini embedding API.
Good quality, generous free tier.

Models:
- embedding-001: General purpose (768 dims)
- text-embedding-004: Newer model (768 dims)
"""

import logging
import os
from typing import List, Optional
import numpy as np
import google.generativeai as genai

from .base import BaseEmbeddingProvider

logger = logging.getLogger(__name__)


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """
    Google Gemini embeddings via API.
    
    Requires GOOGLE_API_KEY or GEMINI_API_KEY environment variable.
    """
    
    MODELS = {
        'models/embedding-001': 768,
        'models/text-embedding-004': 768,
    }
    
    DEFAULT_MODEL = 'models/embedding-001'
    
    # Task types for Gemini embeddings
    TASK_TYPES = [
        'semantic_similarity',
        'retrieval_document',
        'retrieval_query',
        'classification',
        'clustering',
    ]
    
    def __init__(
        self,
        model: str = None,
        dimension: int = None,
        task_type: str = 'semantic_similarity'
    ):
        model = model or self.DEFAULT_MODEL
        dimension = dimension or self.MODELS.get(model, 768)
        super().__init__(model, dimension)
        self.task_type = task_type
        self._configured = False
    
    def _configure(self):
        """Configure Gemini API"""
        if not self._configured:
            api_key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
            genai.configure(api_key=api_key)
            self._configured = True
    
    def is_available(self) -> bool:
        """Check if Gemini is available"""
        try:
            import google.generativeai
            return bool(
                os.environ.get('GOOGLE_API_KEY') or 
                os.environ.get('GEMINI_API_KEY')
            )
        except ImportError:
            return False
    
    def embed(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding for single text"""
        if not text or not text.strip():
            return None
        
        try:
            self._configure()
            
            result = genai.embed_content(
                model=self.model,
                content=text.strip()[:8000],
                task_type=self.task_type
            )
            return np.array(result['embedding'], dtype=np.float32)
        except Exception as e:
            logger.error(f"Gemini embedding failed: {e}")
            return None
    
    def embed_batch(self, texts: List[str]) -> List[Optional[np.ndarray]]:
        """Batch embedding - Gemini supports batch API"""
        if not texts:
            return []
        
        try:
            self._configure()
            
            # Filter valid texts
            valid_indices = []
            valid_texts = []
            for i, text in enumerate(texts):
                if text and text.strip():
                    valid_indices.append(i)
                    valid_texts.append(text.strip()[:8000])
            
            if not valid_texts:
                return [None] * len(texts)
            
            # Batch request
            result = genai.embed_content(
                model=self.model,
                content=valid_texts,
                task_type=self.task_type
            )
            
            # Map back to original indices
            results = [None] * len(texts)
            embeddings = result['embedding']
            
            # Handle both single and batch response formats
            if isinstance(embeddings[0], list):
                # Batch response
                for i, idx in enumerate(valid_indices):
                    results[idx] = np.array(embeddings[i], dtype=np.float32)
            else:
                # Single response
                results[valid_indices[0]] = np.array(embeddings, dtype=np.float32)
            
            return results
            
        except Exception as e:
            logger.error(f"Gemini batch embedding failed: {e}")
            # Fallback to individual calls
            return super().embed_batch(texts)