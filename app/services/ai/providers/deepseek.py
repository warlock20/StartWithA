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
DeepSeek AI Provider Implementation

Uses the OpenAI-compatible API at https://api.deepseek.com.
Supports DeepSeek-V3 (general) and DeepSeek-R1 (reasoning).

Usage:
    from app.services.ai.providers import DeepseekProvider
    from app.services.ai.config import AIModel

    provider = DeepseekProvider()
    response = provider.generate_text("Analyze this investment thesis...")

    # With reasoning model
    provider = DeepseekProvider(model=AIModel.DEEPSEEK_R1)
"""

import json
import logging
from typing import Dict, List, Optional, Any

from .base import AIProvider
from ..config import get_ai_config, AIModel, AIProvider as AIProviderEnum
from ..analytics import log_prompt_usage
from app.utils.time_utils import now_utc

logger = logging.getLogger(__name__)

# ============================================================
# Module-level OpenAI client initialization (for DeepSeek)
# ============================================================

DEEPSEEK_BASE_URL = "https://api.deepseek.com"

_openai_available = False
_openai_module = None


def _initialize_openai():
    """
    Initialize OpenAI SDK (used for DeepSeek's compatible API).

    Returns True if the openai package is importable, False otherwise.
    """
    global _openai_available, _openai_module

    if _openai_module is not None:
        return _openai_available

    try:
        import openai
        _openai_module = openai
        _openai_available = True
        logger.debug("OpenAI library loaded for DeepSeek provider")
        return True

    except ImportError:
        logger.info(
            "openai package not installed. "
            "Install with: pip install openai"
        )
        _openai_available = False
        return False


class DeepseekProvider(AIProvider):
    """
    DeepSeek AI provider using the OpenAI-compatible API.

    DeepSeek models:
    - deepseek-chat (V3): General-purpose, cost-effective
    - deepseek-reasoner (R1): Advanced reasoning, chain-of-thought

    Features:
    - OpenAI SDK compatible (drop-in)
    - JSON mode support
    - Cost-effective for high-volume tasks
    """

    def __init__(self, model: Optional[AIModel] = None):
        """
        Initialize DeepSeek provider.

        Args:
            model: AIModel to use (defaults to DEEPSEEK_V3)
        """
        self._config = get_ai_config()

        _initialize_openai()

        # Set model
        if model is not None:
            if model.provider != AIProviderEnum.DEEPSEEK:
                raise ValueError(f"Model {model.model_id} is not a DeepSeek model")
            self._model_enum = model
        else:
            self._model_enum = AIModel.DEEPSEEK_V3

        # Create client
        self._client = None
        if _openai_available and self._config.deepseek_api_key:
            try:
                self._client = _openai_module.OpenAI(
                    api_key=self._config.deepseek_api_key,
                    base_url=DEEPSEEK_BASE_URL,
                )
                logger.debug(f"DeepseekProvider created with model: {self._model_enum.model_id}")
            except Exception as e:
                logger.error(f"Failed to create DeepSeek client: {e}")

    @property
    def model_name(self) -> str:
        """Get current model name."""
        return self._model_enum.model_id

    def is_available(self) -> bool:
        """Check if DeepSeek provider is available."""
        return _openai_available and self._client is not None

    def generate_text(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
        system: Optional[str] = None,
        prompt_name: Optional[str] = None,
        prompt_version: str = "1.0",
        **kwargs
    ) -> str:
        """
        Generate text using DeepSeek.

        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-2.0)
            top_p: Nucleus sampling threshold
            top_k: Not supported by DeepSeek (ignored)
            stop_sequences: Stop sequences
            system: System prompt
            prompt_name: For analytics tracking
            prompt_version: For analytics tracking
            **kwargs: Additional parameters

        Returns:
            Generated text response
        """
        if not self.is_available():
            raise RuntimeError(
                "DeepSeek provider is not available. "
                "Check DEEPSEEK_API_KEY environment variable and openai package."
            )

        start_time = now_utc()
        input_tokens = None
        output_tokens = None
        success = True
        error_message = None

        try:
            messages = []

            # System message
            if system:
                messages.append({"role": "system", "content": system})

            # User message
            messages.append({"role": "user", "content": prompt})

            # Build request params
            create_params = {
                "model": self._model_enum.model_id,
                "messages": messages,
            }

            if max_tokens is not None:
                create_params["max_tokens"] = max_tokens
            else:
                create_params["max_tokens"] = self._config.default_max_tokens

            if temperature is not None:
                create_params["temperature"] = temperature
            else:
                create_params["temperature"] = self._config.default_temperature

            if top_p is not None:
                create_params["top_p"] = top_p

            if stop_sequences:
                create_params["stop"] = stop_sequences

            response = self._client.chat.completions.create(**create_params)

            # Extract usage
            if response.usage:
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens

            # Extract text
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content
            else:
                raise ValueError("Empty response from DeepSeek")

        except Exception as e:
            success = False
            error_message = str(e)
            logger.error(f"DeepSeek generate_text error: {error_message}")
            raise

        finally:
            end_time = now_utc()
            latency_ms = int((end_time - start_time).total_seconds() * 1000)

            if prompt_name:
                log_prompt_usage(
                    prompt_name=prompt_name,
                    prompt_version=prompt_version,
                    provider="deepseek",
                    model=self._model_enum.model_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    success=success,
                    error_message=error_message,
                )

    def generate_json(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        prompt_name: Optional[str] = None,
        prompt_version: str = "1.0",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate structured JSON response using DeepSeek.

        Uses JSON mode via response_format when available.

        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling threshold
            top_k: Ignored (not supported)
            prompt_name: For analytics tracking
            prompt_version: For analytics tracking
            **kwargs: Additional parameters (system, etc.)

        Returns:
            Parsed JSON dictionary
        """
        if not self.is_available():
            raise RuntimeError("DeepSeek provider is not available")

        # Build messages with JSON instruction
        json_prompt = f"""{prompt}

IMPORTANT: Respond ONLY with valid JSON. No markdown code blocks, no explanation before or after, just the raw JSON object."""

        messages = []
        system = kwargs.get('system', "You are a helpful assistant that responds only with valid JSON.")
        messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": json_prompt})

        start_time = now_utc()
        input_tokens = None
        output_tokens = None
        success = True
        error_message = None

        try:
            create_params = {
                "model": self._model_enum.model_id,
                "messages": messages,
                "max_tokens": max_tokens or self._config.default_max_tokens,
                "temperature": temperature if temperature is not None else 0.3,
                "response_format": {"type": "json_object"},
            }

            if top_p is not None:
                create_params["top_p"] = top_p

            response = self._client.chat.completions.create(**create_params)

            # Extract usage
            if response.usage:
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens

            # Extract text
            if not response.choices or not response.choices[0].message.content:
                raise ValueError("Empty response from DeepSeek")

            text = response.choices[0].message.content.strip()

            # Clean up markdown code blocks if present (fallback)
            if text.startswith('```json'):
                text = text[7:]
            elif text.startswith('```'):
                text = text[3:]
            if text.endswith('```'):
                text = text[:-3]

            return json.loads(text.strip())

        except json.JSONDecodeError as e:
            success = False
            error_message = f"JSON parse error: {e}"
            logger.error(f"DeepSeek JSON parse error: {e}")
            raise ValueError(f"Failed to parse JSON response: {e}")
        except Exception as e:
            success = False
            error_message = str(e)
            logger.error(f"DeepSeek generate_json error: {e}")
            raise

        finally:
            end_time = now_utc()
            latency_ms = int((end_time - start_time).total_seconds() * 1000)

            if prompt_name:
                log_prompt_usage(
                    prompt_name=prompt_name,
                    prompt_version=prompt_version,
                    provider="deepseek",
                    model=self._model_enum.model_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    success=success,
                    error_message=error_message,
                )

    def generate_embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        """
        Generate embeddings — not supported by DeepSeek.

        Falls back to sentence-transformers.
        """
        try:
            from sentence_transformers import SentenceTransformer

            model_name = kwargs.get('model', 'all-MiniLM-L6-v2')

            if not hasattr(self, '_embedding_model'):
                self._embedding_model = SentenceTransformer(model_name)
                logger.info(f"Loaded sentence-transformers ({model_name}) for DeepSeek embeddings fallback")

            return [self._embedding_model.encode(text).tolist() for text in texts]

        except ImportError:
            raise NotImplementedError(
                "DeepSeek doesn't support native embeddings. "
                "Install sentence-transformers for fallback: pip install sentence-transformers"
            )
