"""
Base Embedding Provider

Abstract base class for all embedding providers.
Follows the same pattern as text generation providers.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
import numpy as np


class BaseEmbeddingProvider(ABC):
    """
    Abstract base class for embedding providers.
    
    All embedding providers must implement:
    - embed(): Generate embedding for single text
    - embed_batch(): Generate embeddings for multiple texts
    - is_available(): Check if provider is available
    """
    
    def __init__(self, model: str, dimension: int):
        """
        Initialize embedding provider.
        
        Args:
            model: Model identifier
            dimension: Output embedding dimension
        """
        self.model = model
        self.dimension = dimension
    
    @property
    def name(self) -> str:
        """Provider name for logging/display"""
        return self.__class__.__name__.replace('EmbeddingProvider', '')
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this provider is available.
        
        Returns:
            True if provider can be used
        """
        pass
    
    @abstractmethod
    def embed(self, text: str) -> Optional[np.ndarray]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as numpy array, or None if failed
        """
        pass
    
    def embed_batch(self, texts: List[str]) -> List[Optional[np.ndarray]]:
        """
        Generate embeddings for multiple texts.
        
        Default implementation calls embed() for each text.
        Override for batch-optimized providers.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        return [self.embed(text) for text in texts]
    
    def compute_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray
    ) -> float:
        """
        Compute cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Similarity score between -1 and 1
        """
        if embedding1 is None or embedding2 is None:
            return 0.0
        
        if len(embedding1) != len(embedding2):
            return 0.0
        
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))