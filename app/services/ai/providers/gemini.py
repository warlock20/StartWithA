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

            # New SDK syntax: client.models.generate_content
            response = self._client.models.generate_content(
                model=self._model_enum.model_id,
                contents=prompt,
                config=config_dict
            )

            content = response.text
            if not content:
                raise ValueError("Received empty response from Gemini")

            return json.loads(content.strip())

        except json.JSONDecodeError as e:
            logger.error(f"Gemini JSON parse error: {e}")
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
            # Truncated response — attempt repair by closing open braces/brackets
            logger.warning(f"Truncated JSON detected ({brace_count} unclosed braces). Attempting repair.")
            json_str = content[start_idx:]
            # Strip trailing incomplete string/value
            json_str = json_str.rstrip()
            # Remove trailing comma or incomplete key/value
            if json_str.endswith(','):
                json_str = json_str[:-1]
            # Try closing unclosed brackets/braces
            # Count open brackets too
            bracket_count = json_str.count('[') - json_str.count(']')
            # Remove any trailing incomplete string literal
            last_quote = json_str.rfind('"')
            if last_quote > 0:
                # Check if the quote count is odd (unclosed string)
                quote_count = json_str.count('"')
                if quote_count % 2 != 0:
                    # Truncate to last complete key-value, close the string
                    json_str = json_str[:last_quote + 1]
            # Strip trailing comma again after truncation
            json_str = json_str.rstrip().rstrip(',')
            # Close open brackets and braces
            json_str += ']' * max(0, bracket_count)
            json_str += '}' * max(0, brace_count)
            try:
                result = json.loads(json_str)
                logger.info("Successfully repaired truncated JSON response")
                return result
            except json.JSONDecodeError as repair_err:
                logger.error(f"JSON repair failed: {repair_err}")
                raise ValueError(f"Truncated JSON could not be repaired: {repair_err}")

        json_str = content[start_idx:end_idx]
        return json.loads(json_str)
