"""
Abstract Base Class for AI Providers

This module defines the interface that all AI providers must implement.
This allows easy swapping between providers (Gemini, Claude, OpenAI)
without changing the service layer code.

Usage:
    from app.services.ai.providers.base import AIProvider
    
    class MyProvider(AIProvider):
        def generate_text(self, prompt, **kwargs):
            # Implementation
            pass
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class AIProvider(ABC):
    """
    Abstract interface for AI providers.
    
    All AI providers (Gemini, Claude, OpenAI) must implement this interface
    to ensure consistent behavior across the platform.
    """

    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
        **kwargs
    ) -> str:
        """
        Generate text completion from a prompt.

        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens to generate (provider default if None)
            temperature: Sampling temperature 0.0-2.0 (lower = more deterministic)
            top_p: Nucleus sampling threshold 0.0-1.0
            top_k: Limits token selection pool
            stop_sequences: List of strings to stop generation
            **kwargs: Provider-specific parameters (safety_settings, thinking, system, etc.)

        Returns:
            Generated text response

        Raises:
            RuntimeError: If provider is not available
            Exception: If API call fails
        """
        pass

    @abstractmethod
    def generate_json(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate structured JSON response.

        The prompt should instruct the model to return JSON.
        Implementation should handle JSON parsing and validation.

        Args:
            prompt: The input prompt (should request JSON output)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature 0.0-2.0
            top_p: Nucleus sampling threshold 0.0-1.0
            top_k: Limits token selection pool
            **kwargs: Provider-specific parameters (schema, etc.)

        Returns:
            Parsed JSON as dictionary

        Raises:
            RuntimeError: If provider is not available
            ValueError: If response is not valid JSON
            Exception: If API call fails
        """
        pass

    @abstractmethod
    def generate_embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        """
        Generate vector embeddings for semantic similarity.

        Args:
            texts: List of text strings to embed
            **kwargs: Provider-specific parameters

        Returns:
            List of embedding vectors (one per input text)

        Raises:
            RuntimeError: If provider is not available
            NotImplementedError: If provider doesn't support embeddings
            Exception: If API call fails
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

    @property
    @abstractmethod
    def model_name(self) -> str:
        """
        Get the current model name/identifier.

        Returns:
            Model name string (e.g., 'gemini-2.5-flash', 'claude-sonnet-4-20250514')
        """
        pass

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        
        Default implementation uses rough approximation.
        Override for provider-specific token counting.

        Args:
            text: Input text

        Returns:
            Estimated token count
        """
        # Rough approximation: 1 token ≈ 4 characters for English
        # This is a fallback - providers should override with accurate counting
        return len(text) // 4

    def validate_response(self, response: str) -> str:
        """
        Validate and clean response text.
        
        Override for provider-specific validation.

        Args:
            response: Raw response from provider

        Returns:
            Cleaned response text
        """
        if response is None:
            raise ValueError("Received None response from provider")
        return response.strip()

    def __repr__(self) -> str:
        """String representation of provider"""
        available = "available" if self.is_available() else "unavailable"
        return f"<{self.__class__.__name__} model={self.model_name} {available}>"
