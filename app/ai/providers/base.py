"""
Abstract Base Class for AI Providers

This allows easy swapping between different AI providers (Gemini, OpenAI, Claude, etc.)
without changing the service layer code.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class AIProvider(ABC):
    """Abstract interface for AI providers"""

    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """
        Generate text completion from a prompt.

        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1, lower = more deterministic)
            **kwargs: Provider-specific parameters

        Returns:
            Generated text response
        """
        pass

    @abstractmethod
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate vector embeddings for semantic similarity.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the provider is available and configured.

        Returns:
            True if API key is set and provider is accessible
        """
        pass

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        Default implementation: rough approximation.
        Override for provider-specific token counting.

        Args:
            text: Input text

        Returns:
            Estimated token count
        """
        # Rough approximation: 1 token ≈ 4 characters for English
        return len(text) // 4
