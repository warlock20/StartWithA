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
TF-IDF Embedding Provider

Fallback provider that always works.
Uses scikit-learn's TF-IDF vectorizer.

No API key required, but lower quality than neural embeddings.
"""

import logging
from typing import List, Optional
import numpy as np

from .base import BaseEmbeddingProvider

logger = logging.getLogger(__name__)


class TfidfEmbeddingProvider(BaseEmbeddingProvider):
    """
    TF-IDF based embeddings as fallback.
    
    Advantages:
    - Always works (no API needed)
    - Fast
    - Deterministic
    
    Disadvantages:
    - Lower quality than neural embeddings
    - No semantic understanding
    - Vocabulary limited to training corpus
    """
    
    DEFAULT_DIMENSION = 512
    
    def __init__(self, model: str = 'tfidf', dimension: int = None):
        dimension = dimension or self.DEFAULT_DIMENSION
        super().__init__(model, dimension)
        self._vectorizer = None
        self._initialized = False
    
    def _init_vectorizer(self):
        """Initialize and fit TF-IDF vectorizer"""
        if self._initialized:
            return
        
        from sklearn.feature_extraction.text import TfidfVectorizer
        
        self._vectorizer = TfidfVectorizer(
            max_features=self.dimension,
            stop_words='english',
            ngram_range=(1, 2),
            sublinear_tf=True,  # Use log(tf) for better results
            norm='l2'  # L2 normalize for cosine similarity
        )
        
        # Fit on financial vocabulary
        financial_corpus = [
            "investment thesis valuation growth revenue earnings profit margin cashflow",
            "risk downside competition market share decline regulatory threat moat",
            "catalyst earnings announcement product launch acquisition merger expansion",
            "bull bear bullish bearish long short position portfolio allocation",
            "dividend yield price target fair value intrinsic value DCF model",
            "PE ratio EV EBITDA revenue multiple growth rate return ROIC ROE",
            "balance sheet income statement cash flow debt equity assets liabilities",
            "management team executive leadership strategy vision competitive advantage",
            "sector industry technology healthcare financial consumer cyclical defensive",
            "momentum trend support resistance technical analysis fundamental analysis",
            "overconfidence bias anchoring recency confirmation behavioral pattern",
            "research checklist due diligence analysis evaluation recommendation",
        ]
        
        self._vectorizer.fit(financial_corpus)
        self._initialized = True
        logger.info("TF-IDF vectorizer initialized with financial vocabulary")
    
    def is_available(self) -> bool:
        """Check if sklearn is available"""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            return True
        except ImportError:
            return False
    
    def embed(self, text: str) -> Optional[np.ndarray]:
        """Generate TF-IDF embedding for single text"""
        if not text or not text.strip():
            return None
        
        try:
            self._init_vectorizer()
            
            # Transform text
            vector = self._vectorizer.transform([text.strip()]).toarray()[0]
            
            # Pad to expected dimension if needed
            if len(vector) < self.dimension:
                vector = np.pad(vector, (0, self.dimension - len(vector)))
            
            return vector.astype(np.float32)
            
        except Exception as e:
            logger.error(f"TF-IDF embedding failed: {e}")
            return None
    
    def embed_batch(self, texts: List[str]) -> List[Optional[np.ndarray]]:
        """Batch TF-IDF embedding"""
        if not texts:
            return []
        
        try:
            self._init_vectorizer()
            
            # Filter valid texts
            valid_indices = []
            valid_texts = []
            for i, text in enumerate(texts):
                if text and text.strip():
                    valid_indices.append(i)
                    valid_texts.append(text.strip())
            
            if not valid_texts:
                return [None] * len(texts)
            
            # Batch transform
            vectors = self._vectorizer.transform(valid_texts).toarray()
            
            # Map back to original indices with padding
            results = [None] * len(texts)
            for i, idx in enumerate(valid_indices):
                vector = vectors[i]
                if len(vector) < self.dimension:
                    vector = np.pad(vector, (0, self.dimension - len(vector)))
                results[idx] = vector.astype(np.float32)
            
            return results
            
        except Exception as e:
            logger.error(f"TF-IDF batch embedding failed: {e}")
            return [None] * len(texts)