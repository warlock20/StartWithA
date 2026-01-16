"""
Google Gemini AI Provider Implementation

This provider handles all interactions with Google's Gemini API.
It uses centralized configuration and ensures single initialization.

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
import google.generativeai as genai

from .base import AIProvider
from ..config import get_ai_config, AIModel, AIProvider as AIProviderEnum

logger = logging.getLogger(__name__)

# ============================================================
# Module-level Gemini initialization (happens once)
# ============================================================

_gemini_available = False
_genai = None


def _initialize_gemini():
    """
    Initialize Gemini API exactly once at module level.
    
    This prevents multiple configurations which can cause issues.
    """
    global _gemini_available, _genai
    
    if _genai is not None:
        return _gemini_available
    
    try:
        _genai = genai
        
        config = get_ai_config()
        if not config.gemini_api_key:
            logger.warning("Gemini API key not found in environment")
            _gemini_available = False
            return False
        
        # Configure Gemini API (once)
        genai.configure(
            api_key=config.gemini_api_key,
            transport='rest',
            client_options={'api_endpoint': 'https://generativelanguage.googleapis.com'}
        )
        
        _gemini_available = True
        logger.info("Gemini API initialized successfully")
        return True
        
    except ImportError:
        logger.error("google-generativeai package not installed. "
                    "Install with: pip install google-generativeai")
        _gemini_available = False
        return False
    except Exception as e:
        logger.error(f"Failed to initialize Gemini API: {e}")
        _gemini_available = False
        return False


class GeminiProvider(AIProvider):
    """
    Google Gemini AI provider implementation.
    
    Features:
    - Centralized configuration
    - Single API initialization
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
        
        # Ensure Gemini is initialized
        _initialize_gemini()
        
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
        
        # Create model instance
        self._model = None
        if _gemini_available and _genai is not None:
            try:
                self._model = _genai.GenerativeModel(self._model_enum.model_id)
                logger.debug(f"GeminiProvider created with model: {self._model_enum.model_id}")
            except Exception as e:
                logger.error(f"Failed to create Gemini model: {e}")

    @property
    def model_name(self) -> str:
        """Get current model name"""
        return self._model_enum.model_id

    def is_available(self) -> bool:
        """Check if Gemini provider is available"""
        return _gemini_available and self._model is not None

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
            **kwargs: Gemini-specific parameters (safety_settings, etc.)

        Returns:
            Generated text response
        """
        if not self.is_available():
            raise RuntimeError(
                "Gemini provider is not available. "
                "Check GEMINI_API_KEY environment variable."
            )

        try:
            # Build generation config
            generation_config = {}
            if max_tokens is not None:
                generation_config['max_output_tokens'] = max_tokens
            if temperature is not None:
                generation_config['temperature'] = temperature
            if top_p is not None:
                generation_config['top_p'] = top_p
            if top_k is not None:
                generation_config['top_k'] = top_k
            if stop_sequences is not None:
                generation_config['stop_sequences'] = stop_sequences

            # Extract timeout if provided
            timeout = kwargs.pop('timeout', self._config.default_timeout)
            request_options = {"timeout": timeout}

            # Get safety settings
            safety_settings = kwargs.pop('safety_settings', self._get_default_safety_settings())

            # Handle system context (Gemini uses system_instruction)
            system_context = kwargs.get('system')
            logger.info(f"Gemini TEXT: Checking system context - Found: {system_context is not None}, kwargs keys: {list(kwargs.keys())}")
            if system_context:
                logger.info(f"Gemini: Using system_instruction (length: {len(system_context)} chars)")
                logger.debug(f"Gemini system_instruction: {system_context[:200]}...")
                # Create model with system instruction
                model_with_system = _genai.GenerativeModel(
                    self._model_enum.model_id,
                    system_instruction=system_context
                )
                response = model_with_system.generate_content(
                    prompt,
                    generation_config=generation_config if generation_config else None,
                    safety_settings=safety_settings,
                    request_options=request_options
                )
            else:
                logger.debug("Gemini: No system_instruction provided")
                response = self._model.generate_content(
                    prompt,
                    generation_config=generation_config if generation_config else None,
                    safety_settings=safety_settings,
                    request_options=request_options
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
            **kwargs: Additional parameters (timeout, safety_settings)

        Returns:
            Parsed JSON dictionary
        """
        if not self.is_available():
            raise RuntimeError("Gemini provider is not available")

        try:
            # Build generation config with JSON mode
            config_dict = {
                "response_mime_type": "application/json"
            }

            if schema:
                config_dict["response_schema"] = schema
            if max_tokens is not None:
                config_dict["max_output_tokens"] = max_tokens
            if temperature is not None:
                config_dict["temperature"] = temperature
            if top_p is not None:
                config_dict["top_p"] = top_p
            if top_k is not None:
                config_dict["top_k"] = top_k

            generation_config = _genai.types.GenerationConfig(**config_dict)

            timeout = kwargs.get('timeout', self._config.default_timeout)
            request_options = {"timeout": timeout}

            # Handle system context (Gemini uses system_instruction)
            # If system context is provided, create a new model instance with it
            system_context = kwargs.get('system')
            logger.info(f"Gemini JSON: Checking system context - Found: {system_context is not None}, kwargs keys: {list(kwargs.keys())}")
            if system_context:
                logger.info(f"Gemini JSON: Using system_instruction (length: {len(system_context)} chars)")
                logger.info(f"Gemini JSON system_instruction: {system_context[:200]}...")
                # Create model with system instruction
                model_with_system = _genai.GenerativeModel(
                    self._model_enum.model_id,
                    system_instruction=system_context
                )
                response = model_with_system.generate_content(
                    prompt,
                    generation_config=generation_config,
                    request_options=request_options
                )
            else:
                logger.info("Gemini JSON: No system_instruction provided")
                response = self._model.generate_content(
                    prompt,
                    generation_config=generation_config,
                    request_options=request_options
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
            task_type = kwargs.get('task_type', 'retrieval_document')
            embedding_model = kwargs.get('model', 'models/embedding-001')

            embeddings = []
            for text in texts:
                result = _genai.embed_content(
                    model=embedding_model,
                    content=text,
                    task_type=task_type
                )
                embeddings.append(result['embedding'])

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
            result = self._model.count_tokens(text)
            return result.total_tokens
        except Exception as e:
            logger.warning(f"Token counting failed, using approximation: {str(e)}")
            return len(text) // 4

    def _get_default_safety_settings(self) -> List[Dict]:
        """
        Get default safety settings for content generation.

        These are permissive settings suitable for business/research content.
        Override via kwargs if stricter settings needed.

        Note: Only using the 4 standard safety categories supported by Gemini SDK.
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
        
        # Handle finish reasons
        # 1=STOP (normal), 2=RECITATION, 3=SAFETY, 4=MAX_TOKENS, 5=OTHER
        finish_reason = candidate.finish_reason
        
        if finish_reason == 2:  # RECITATION
            raise RuntimeError(
                "Content generation blocked due to potential copyright/recitation concerns. "
                "Try rephrasing your prompt or using more original content."
            )
        elif finish_reason == 3:  # SAFETY
            raise RuntimeError(
                "Content generation blocked by safety filters. "
                "Please review your input content."
            )
        elif finish_reason == 4:  # MAX_TOKENS
            logger.warning("Response truncated due to max_tokens limit")
            # Still return partial response
        elif finish_reason not in [1, 4, None]:  # Not STOP, MAX_TOKENS, or unset
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
            raise ValueError("Unmatched braces in JSON response")

        json_str = content[start_idx:end_idx]
        return json.loads(json_str)
