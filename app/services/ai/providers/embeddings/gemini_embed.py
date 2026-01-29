"""
Gemini Embedding Provider

Uses Google's Gemini embedding API with the new google-genai SDK.
Good quality, generous free tier.

Models:
- embedding-001: General purpose (768 dims)
- text-embedding-004: Newer model (768 dims)
"""

import logging
import os
from typing import List, Optional
import numpy as np
from google import genai

from .base import BaseEmbeddingProvider

logger = logging.getLogger(__name__)

# Module-level client singleton
_gemini_client: Optional[genai.Client] = None


def _get_client() -> Optional[genai.Client]:
    """Get or create Gemini client singleton."""
    global _gemini_client

    if _gemini_client is not None:
        return _gemini_client

    api_key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return None

    try:
        _gemini_client = genai.Client(api_key=api_key)
        return _gemini_client
    except Exception as e:
        logger.error(f"Failed to create Gemini client: {e}")
        return None


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """
    Google Gemini embeddings via API.

    Requires GOOGLE_API_KEY or GEMINI_API_KEY environment variable.
    """

    MODELS = {
        'models/embedding-001': 768,
        'models/text-embedding-004': 768,
    }

    DEFAULT_MODEL = 'models/text-embedding-004'

    def __init__(
        self,
        model: str = None,
        dimension: int = None,
    ):
        model = model or self.DEFAULT_MODEL
        dimension = dimension or self.MODELS.get(model, 768)
        super().__init__(model, dimension)
        self._client = _get_client()

    def is_available(self) -> bool:
        """Check if Gemini is available"""
        return self._client is not None

    def embed(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding for single text"""
        if not text or not text.strip():
            return None

        if not self.is_available():
            logger.error("Gemini client not available")
            return None

        try:
            # New SDK syntax: client.models.embed_content
            result = self._client.models.embed_content(
                model=self.model,
                contents=text.strip()[:8000]
            )
            return np.array(result.embeddings[0].values, dtype=np.float32)
        except Exception as e:
            logger.error(f"Gemini embedding failed: {e}")
            return None

    def embed_batch(self, texts: List[str]) -> List[Optional[np.ndarray]]:
        """Batch embedding - process texts individually with new SDK"""
        if not texts:
            return []

        if not self.is_available():
            logger.error("Gemini client not available")
            return [None] * len(texts)

        try:
            results = []
            for text in texts:
                if text and text.strip():
                    # New SDK syntax: client.models.embed_content
                    result = self._client.models.embed_content(
                        model=self.model,
                        contents=text.strip()[:8000]
                    )
                    results.append(np.array(result.embeddings[0].values, dtype=np.float32))
                else:
                    results.append(None)

            return results

        except Exception as e:
            logger.error(f"Gemini batch embedding failed: {e}")
            # Fallback to individual calls
            return super().embed_batch(texts)
