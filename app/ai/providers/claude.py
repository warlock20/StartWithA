"""
Anthropic Claude AI Provider Implementation
"""

import os
import logging
from typing import List, Optional
import anthropic

from .base import AIProvider


logger = logging.getLogger(__name__)


class ClaudeProvider(AIProvider):
    """Anthropic Claude AI provider implementation"""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514"):
        """
        Initialize Claude provider.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Model name to use (default: claude-sonnet-4-20250514)
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        self.model_name = model
        self._client = None

        if self.api_key:
            self._client = anthropic.Anthropic(api_key=self.api_key)
            logger.info(f"Claude provider initialized with model: {self.model_name}")
        else:
            logger.warning("Anthropic API key not found. Provider will not be available.")

    def generate_text(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """
        Generate text completion using Claude.

        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            **kwargs: Additional Claude-specific parameters

        Returns:
            Generated text response

        Raises:
            RuntimeError: If provider is not available
            Exception: If API call fails
        """
        if not self.is_available():
            raise RuntimeError("Claude provider is not available. Check ANTHROPIC_API_KEY configuration.")

        try:
            # Default max_tokens if not specified
            if max_tokens is None:
                max_tokens = 4096

            # Build message parameters
            message_params = {
                "model": self.model_name,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}]
            }

            # Add optional parameters
            if temperature is not None:
                message_params["temperature"] = temperature

            # Add any additional kwargs
            message_params.update(kwargs)

            # Call Claude API
            message = self._client.messages.create(**message_params)

            # Extract text from response
            if not message.content:
                raise RuntimeError("No content returned from Claude API")

            # Claude returns a list of content blocks
            return message.content[0].text

        except Exception as e:
            logger.error(f"Claude API error: {str(e)}")
            raise

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings using Claude.

        Note: Claude does not natively support embeddings.
        This is a placeholder that raises NotImplementedError.

        For embeddings, use:
        - GeminiProvider (has embedding support)
        - OpenAI text-embedding-ada-002
        - Sentence transformers (local models)

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors

        Raises:
            NotImplementedError: Claude doesn't support embeddings
        """
        raise NotImplementedError(
            "Claude does not support embeddings. "
            "Use GeminiProvider or a dedicated embedding model instead."
        )

    def is_available(self) -> bool:
        """
        Check if Claude provider is available.

        Returns:
            True if API key is set and client is initialized
        """
        return self.api_key is not None and self._client is not None

    def count_tokens(self, text: str) -> int:
        """
        Count tokens using Claude's token counter.

        Args:
            text: Input text

        Returns:
            Exact token count from Claude
        """
        if not self.is_available():
            # Fallback to approximation
            return super().count_tokens(text)

        try:
            # Claude's token counting
            result = self._client.count_tokens(text)
            return result

        except Exception as e:
            logger.warning(f"Token counting failed, using approximation: {str(e)}")
            # Fallback: Claude uses ~4 chars per token
            return super().count_tokens(text)
