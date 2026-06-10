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
Google Gemini AI Provider Implementation

This provider handles all interactions with Google's Gemini API.
Uses the new google-genai SDK with Client object pattern.

Usage:
    from app.services.ai.providers import GeminiProvider
    from app.services.ai.config import AIModel

    # Default model from config
    provider = GeminiProvider()

    # Specific model
    provider = GeminiProvider(model=AIModel.GEMINI_PRO_25)

    # Generate text
    response = provider.generate_text("Analyze this company...")
"""

import json
import logging
from typing import Dict, List, Optional, Any
from google import genai
from google.genai import types as genai_types

from .base import AIProvider
from ..config import get_ai_config, AIModel, AIProvider as AIProviderEnum

logger = logging.getLogger(__name__)

# ============================================================
# Module-level Gemini Client (singleton pattern)
# ============================================================

_gemini_client: Optional[genai.Client] = None


def _get_gemini_client() -> Optional[genai.Client]:
    """
    Get or create the Gemini Client (singleton).

    In the new google-genai SDK, we use a Client object
    instead of global configuration.
    """
    global _gemini_client

    if _gemini_client is not None:
        return _gemini_client

    try:
        config = get_ai_config()
        if not config.gemini_api_key:
            logger.warning("Gemini API key not found in environment")
            return None

        # Create client with API key
        _gemini_client = genai.Client(api_key=config.gemini_api_key)
        logger.info("Gemini Client initialized successfully")
        return _gemini_client

    except ImportError:
        logger.error("google-genai package not installed. "
                    "Install with: pip install google-genai")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Gemini Client: {e}")
        return None


class GeminiProvider(AIProvider):
    """
    Google Gemini AI provider implementation.

    Features:
    - Centralized configuration via Client object
    - JSON response support
    - Embedding generation
    - Token counting
    - Configurable safety settings
    """

    def __init__(self, model: Optional[AIModel] = None):
        """
        Initialize Gemini provider.

        Args:
            model: AIModel to use (defaults to config default_model)
        """
        self._config = get_ai_config()
        self._client = _get_gemini_client()

        # Set model
        if model is not None:
            if model.provider != AIProviderEnum.GEMINI:
                raise ValueError(f"Model {model.model_id} is not a Gemini model")
            self._model_enum = model
        else:
            # Use default from config (ensure it's a Gemini model)
            default = self._config.default_model
            if default.provider == AIProviderEnum.GEMINI:
                self._model_enum = default
            else:
                self._model_enum = AIModel.GEMINI_FLASH_25

        logger.debug(f"GeminiProvider created with model: {self._model_enum.model_id}")

    @property
    def model_name(self) -> str:
        """Get current model name"""
        return self._model_enum.model_id

    def is_available(self) -> bool:
        """Check if Gemini provider is available"""
        return self._client is not None

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
        Generate text completion using Gemini.

        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-2.0)
            top_p: Nucleus sampling threshold (0.0-1.0)
            top_k: Limits token selection pool
            stop_sequences: List of strings to stop generation
            **kwargs: Additional parameters (system, timeout, safety_settings)

        Returns:
            Generated text response
        """
        if not self.is_available():
            raise RuntimeError(
                "Gemini provider is not available. "
                "Check GEMINI_API_KEY environment variable."
            )

        try:
            # Build generation config dict
            config_dict = {}
            if max_tokens is not None:
                config_dict['max_output_tokens'] = max_tokens
            if temperature is not None:
                config_dict['temperature'] = temperature
            if top_p is not None:
                config_dict['top_p'] = top_p
            if top_k is not None:
                config_dict['top_k'] = top_k
            if stop_sequences is not None:
                config_dict['stop_sequences'] = stop_sequences

            # Handle system context
            system_context = kwargs.get('system')
            if system_context:
                logger.info(f"Gemini TEXT: Using system_instruction (length: {len(system_context)} chars)")
                config_dict['system_instruction'] = system_context

            # Get safety settings
            safety_settings = kwargs.pop('safety_settings', self._get_default_safety_settings())
            if safety_settings:
                config_dict['safety_settings'] = safety_settings

            # Handle Google Search grounding (for fact-checking, etc.)
            google_search = kwargs.pop('google_search', False)
            if google_search:
                config_dict['tools'] = [genai_types.Tool(google_search=genai_types.GoogleSearch())]
                logger.info("Gemini TEXT: Google Search grounding enabled")

            # New SDK syntax: client.models.generate_content
            response = self._client.models.generate_content(
                model=self._model_enum.model_id,
                contents=prompt,
                config=config_dict if config_dict else None
            )

            return self._process_response(response)

        except Exception as e:
            logger.error(f"Gemini generate_text error: {str(e)}")
            raise

    def generate_json(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        schema: Optional[Dict] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate structured JSON response.

        Uses Gemini's native JSON mode for reliable structured output.

        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-2.0)
            top_p: Nucleus sampling threshold (0.0-1.0)
            top_k: Limits token selection pool
            schema: JSON schema for structured output (Gemini-specific)
            **kwargs: Additional parameters (system, timeout, safety_settings)

        Returns:
            Parsed JSON dictionary
        """
        if not self.is_available():
            raise RuntimeError("Gemini provider is not available")

        response = None
        try:
            # Build config dict with JSON mode
            config_dict = {
                'response_mime_type': 'application/json'
            }

            if schema:
                config_dict['response_schema'] = schema
            if max_tokens is not None:
                config_dict['max_output_tokens'] = max_tokens
            if temperature is not None:
                config_dict['temperature'] = temperature
            if top_p is not None:
                config_dict['top_p'] = top_p
            if top_k is not None:
                config_dict['top_k'] = top_k

            # Handle system context
            system_context = kwargs.get('system')
            if system_context:
                logger.info(f"Gemini JSON: Using system_instruction (length: {len(system_context)} chars)")
                config_dict['system_instruction'] = system_context

            # Apply safety settings (same as generate_text)
            safety_settings = kwargs.pop('safety_settings', self._get_default_safety_settings())
            if safety_settings:
                config_dict['safety_settings'] = safety_settings

            # Retry loop for truncated responses
            max_retries = 3
            last_error = None
            for attempt in range(1, max_retries + 1):
                # New SDK syntax: client.models.generate_content
                response = self._client.models.generate_content(
                    model=self._model_enum.model_id,
                    contents=prompt,
                    config=config_dict
                )

                # Check finish_reason for diagnostics
                truncated = False
                if response.candidates:
                    finish_reason = response.candidates[0].finish_reason
                    if finish_reason == 'MAX_TOKENS':
                        truncated = True
                        current_limit = config_dict.get('max_output_tokens', max_tokens)
                        logger.warning(f"Gemini JSON response truncated (MAX_TOKENS) on attempt {attempt}/{max_retries}. "
                                       f"max_output_tokens={current_limit}, model={self._model_enum.model_id}")
                    elif finish_reason == 'SAFETY':
                        logger.error(f"Gemini JSON response blocked by safety filters on attempt {attempt}")
                    elif finish_reason not in ['STOP', None]:
                        logger.warning(f"Gemini JSON unexpected finish_reason: {finish_reason} on attempt {attempt}")

                content = response.text
                if not content:
                    raise ValueError("Received empty response from Gemini")

                try:
                    return json.loads(content.strip())
                except json.JSONDecodeError as e:
                    logger.error(f"Gemini JSON parse error (attempt {attempt}/{max_retries}): {e}")
                    last_error = e
                    if attempt < max_retries:
                        # If truncated due to MAX_TOKENS, increase the limit for next attempt
                        if truncated:
                            current_limit = config_dict.get('max_output_tokens', max_tokens or 8000)
                            new_limit = int(current_limit * 1.5)
                            config_dict['max_output_tokens'] = new_limit
                            logger.info(f"Increasing max_output_tokens from {current_limit} to {new_limit} for retry")
                        finish_info = ""
                        if response.candidates:
                            finish_info = f" (finish_reason={response.candidates[0].finish_reason})"
                        logger.warning(f"Retrying JSON generation{finish_info}...")
                        continue
                    # Final attempt failed — fall through to fallback extraction
                    break

            # Try to extract JSON from response
            return self._extract_json_fallback(response.text if response else "")
        except Exception as e:
            logger.error(f"Gemini generate_json error: {e}")
            raise

    def generate_embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        """
        Generate embeddings using Gemini embedding model.

        Args:
            texts: List of text strings to embed
            **kwargs: Additional parameters (task_type, model, etc.)

        Returns:
            List of embedding vectors
        """
        if not self.is_available():
            raise RuntimeError("Gemini provider is not available")

        try:
            # Extract optional parameters
            embedding_model = kwargs.get('model', 'models/gemini-embedding-001')

            embeddings = []
            for text in texts:
                # New SDK syntax: client.models.embed_content
                result = self._client.models.embed_content(
                    model=embedding_model,
                    contents=text
                )
                embeddings.append(result.embeddings[0].values)

            return embeddings

        except Exception as e:
            logger.error(f"Gemini embedding error: {str(e)}")
            raise

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
            return len(text) // 4

        try:
            # New SDK syntax: client.models.count_tokens
            result = self._client.models.count_tokens(
                model=self._model_enum.model_id,
                contents=text
            )
            return result.total_tokens
        except Exception as e:
            logger.warning(f"Token counting failed, using approximation: {str(e)}")
            return len(text) // 4

    def _get_default_safety_settings(self) -> List[Dict]:
        """
        Get default safety settings for content generation.

        These are permissive settings suitable for business/research content.
        Override via kwargs if stricter settings needed.
        """
        return [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

    def _process_response(self, response) -> str:
        """
        Process and validate response from Gemini.

        Handles various finish reasons and extracts text.

        Args:
            response: Raw Gemini response

        Returns:
            Extracted text content

        Raises:
            RuntimeError: If response indicates blocking or error
        """
        if not response.candidates:
            raise RuntimeError("No response candidates returned from Gemini API")

        candidate = response.candidates[0]

        # Handle finish reasons (new SDK uses string values)
        finish_reason = candidate.finish_reason

        # Map string values to behavior
        if finish_reason == 'RECITATION':
            raise RuntimeError(
                "Content generation blocked due to potential copyright/recitation concerns. "
                "Try rephrasing your prompt or using more original content."
            )
        elif finish_reason == 'SAFETY':
            raise RuntimeError(
                "Content generation blocked by safety filters. "
                "Please review your input content."
            )
        elif finish_reason == 'MAX_TOKENS':
            logger.warning("Response truncated due to max_tokens limit")
            # Still return partial response
        elif finish_reason not in ['STOP', 'MAX_TOKENS', None]:
            logger.warning(f"Unexpected finish_reason: {finish_reason}")

        return response.text

    def _extract_json_fallback(self, content: str) -> Dict[str, Any]:
        """
        Fallback JSON extraction when native mode fails.

        Attempts to find JSON object in response text.

        Args:
            content: Raw response text

        Returns:
            Extracted JSON dictionary

        Raises:
            ValueError: If no valid JSON found
        """
        if not content:
            raise ValueError("Empty content, cannot extract JSON")

        # Remove markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            parts = content.split("```")
            if len(parts) >= 3:
                content = parts[1].strip()

        content = content.strip()

        # Find JSON object boundaries
        start_idx = content.find('{')
        if start_idx == -1:
            raise ValueError("No JSON object found in response")

        # Find matching closing brace
        brace_count = 0
        end_idx = -1
        for i, char in enumerate(content[start_idx:], start_idx):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break

        if end_idx == -1:
            # Truncated response — attempt repair by closing open structures
            logger.warning(f"Truncated JSON detected ({brace_count} unclosed braces). Attempting repair.")
            json_str = content[start_idx:].rstrip()

            repair_attempts = []

            # Strategy 1: Stack-based repair — parse to build nesting stack, close in correct order
            try:
                s1 = self._stack_based_repair(json_str)
                if s1:
                    repair_attempts.append(("stack-based repair", s1))
            except Exception:
                pass

            # Strategy 2: Truncate to last comma, then stack-based repair
            last_comma = json_str.rfind(',')
            if last_comma > 0:
                try:
                    s2 = self._stack_based_repair(json_str[:last_comma].rstrip())
                    if s2:
                        repair_attempts.append(("truncate to last complete entry", s2))
                except Exception:
                    pass

            # Strategy 3: Truncate to second-to-last comma for deeper cuts
            if last_comma > 0:
                second_comma = json_str.rfind(',', 0, last_comma)
                if second_comma > 0:
                    try:
                        s3 = self._stack_based_repair(json_str[:second_comma].rstrip())
                        if s3:
                            repair_attempts.append(("truncate to second-last entry", s3))
                    except Exception:
                        pass

            for strategy_name, candidate in repair_attempts:
                try:
                    result = json.loads(candidate)
                    logger.info(f"Successfully repaired truncated JSON via strategy: {strategy_name}")
                    return result
                except json.JSONDecodeError:
                    logger.debug(f"Repair strategy '{strategy_name}' failed, trying next...")
                    continue

            raise ValueError(f"Truncated JSON could not be repaired after {len(repair_attempts)} strategies")

        json_str = content[start_idx:end_idx]
        return json.loads(json_str)

    @staticmethod
    def _stack_based_repair(json_str: str) -> str:
        """
        Repair truncated JSON by parsing character-by-character to build a nesting
        stack, then closing structures in the correct reverse order.

        Returns the repaired JSON string, or empty string on failure.
        """
        stack = []  # tracks '{' or '['
        in_string = False
        escaped = False
        i = 0

        while i < len(json_str):
            ch = json_str[i]
            if escaped:
                escaped = False
                i += 1
                continue
            if ch == '\\' and in_string:
                escaped = True
                i += 1
                continue
            if ch == '"':
                in_string = not in_string
            elif not in_string:
                if ch in ('{', '['):
                    stack.append(ch)
                elif ch == '}':
                    if stack and stack[-1] == '{':
                        stack.pop()
                elif ch == ']':
                    if stack and stack[-1] == '[':
                        stack.pop()
            i += 1

        if not stack:
            return json_str

        # Close unterminated string if needed
        result = json_str
        if in_string:
            result += '"'

        # Strip trailing comma or colon (incomplete key-value pair)
        result = result.rstrip()
        if result.endswith(',') or result.endswith(':'):
            result = result[:-1].rstrip()

        # Close structures in reverse nesting order
        closers = {'{': '}', '[': ']'}
        for opener in reversed(stack):
            result += closers[opener]

        return result
