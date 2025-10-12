"""
Google Gemini AI Provider Implementation
"""

import os
import logging
from typing import List, Optional
import google.generativeai as genai

from .base import AIProvider


logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    """Google Gemini AI provider implementation"""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash"):
        """
        Initialize Gemini provider.

        Args:
            api_key: Gemini API key (defaults to GEMINI_API_KEY env var)
            model: Model name to use (default: gemini-2.5-flash)
        """
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        self.model_name = model
        self._model = None

        if self.api_key:
            # Configure with API v1 endpoint
            genai.configure(
                api_key=self.api_key,
                transport='rest',
                client_options={'api_endpoint': 'https://generativelanguage.googleapis.com'}
            )
            self._model = genai.GenerativeModel(self.model_name)
            logger.info(f"Gemini provider initialized with model: {self.model_name}")
        else:
            logger.warning("Gemini API key not found. Provider will not be available.")

    def generate_text(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """
        Generate text completion using Gemini.

        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            **kwargs: Additional Gemini-specific parameters

        Returns:
            Generated text response

        Raises:
            RuntimeError: If provider is not available
            Exception: If API call fails
        """
        if not self.is_available():
            raise RuntimeError("Gemini provider is not available. Check API key configuration.")

        try:
            # Build generation config
            generation_config = {}
            if max_tokens:
                generation_config['max_output_tokens'] = max_tokens
            if temperature is not None:
                generation_config['temperature'] = temperature

            # Merge with any additional kwargs
            generation_config.update(kwargs)

            # Configure safety settings to be more permissive for business/research content
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE"
                }
            ]

            # Generate content
            response = self._model.generate_content(
                prompt,
                generation_config=generation_config if generation_config else None,
                safety_settings=safety_settings
            )

            # Check if response has valid content
            if not response.candidates:
                raise RuntimeError("No response candidates returned from Gemini API")

            candidate = response.candidates[0]

            # Handle different finish reasons
            # finish_reason: 1=STOP (normal), 2=RECITATION, 3=SAFETY, 4=MAX_TOKENS, 5=OTHER
            if candidate.finish_reason == 2:  # RECITATION
                raise RuntimeError(
                    "Content generation blocked due to potential copyright/recitation concerns. "
                    "Try rephrasing your prompt or using more original content."
                )
            elif candidate.finish_reason == 3:  # SAFETY
                raise RuntimeError(
                    "Content generation blocked by safety filters. "
                    "Please review your input content."
                )
            elif candidate.finish_reason == 4:  # MAX_TOKENS
                logger.warning("Response truncated due to max_tokens limit")
                # Still return partial response
            elif candidate.finish_reason not in [1, 4]:  # Not STOP or MAX_TOKENS
                raise RuntimeError(f"Unexpected finish_reason: {candidate.finish_reason}")

            return response.text

        except Exception as e:
            logger.error(f"Gemini API error: {str(e)}")
            raise

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings using Gemini embedding model.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors

        Raises:
            RuntimeError: If provider is not available
            Exception: If API call fails
        """
        if not self.is_available():
            raise RuntimeError("Gemini provider is not available. Check API key configuration.")

        try:
            embeddings = []
            for text in texts:
                result = genai.embed_content(
                    model="models/embedding-001",
                    content=text,
                    task_type="retrieval_document"
                )
                embeddings.append(result['embedding'])

            return embeddings

        except Exception as e:
            logger.error(f"Gemini embedding error: {str(e)}")
            raise

    def is_available(self) -> bool:
        """
        Check if Gemini provider is available.

        Returns:
            True if API key is set and model is initialized
        """
        return self.api_key is not None and self._model is not None

    def count_tokens(self, text: str) -> int:
        """
        Count tokens using Gemini's token counter.

        Args:
            text: Input text

        Returns:
            Exact token count from Gemini
        """
        if not self.is_available():
            # Fallback to approximation
            return super().count_tokens(text)

        try:
            result = self._model.count_tokens(text)
            return result.total_tokens
        except Exception as e:
            logger.warning(f"Token counting failed, using approximation: {str(e)}")
            return super().count_tokens(text)
