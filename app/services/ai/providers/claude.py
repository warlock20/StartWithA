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
Anthropic Claude AI Provider Implementation

This provider handles all interactions with Anthropic's Claude API.
Claude excels at complex reasoning tasks like thesis analysis and pattern explanation.

Usage:
    from app.services.ai.providers import ClaudeProvider
    from app.services.ai.config import AIModel
    
    # Default model (Claude Sonnet)
    provider = ClaudeProvider()
    
    # Specific model
    provider = ClaudeProvider(model=AIModel.CLAUDE_OPUS)
    
    # Generate text
    response = provider.generate_text("Analyze this investment thesis...")
    
    # Investment-specific methods
    analysis = provider.analyze_thesis(company, thesis, data)
    warning = provider.generate_warning(context, patterns)
"""

import json
import logging
from typing import Dict, List, Optional, Any

from .base import AIProvider
from ..config import get_ai_config, AIModel, AIProvider as AIProviderEnum
from ..prompt_service import get_intelligence_prompt
from ..analytics import log_prompt_usage
from app.utils.time_utils import now_utc

logger = logging.getLogger(__name__)

# ============================================================
# Module-level Claude initialization
# ============================================================

_anthropic_available = False
_anthropic = None


def _initialize_anthropic():
    """
    Initialize Anthropic client.
    
    Returns True if successful, False otherwise.
    """
    global _anthropic_available, _anthropic
    
    if _anthropic is not None:
        return _anthropic_available
    
    try:
        import anthropic
        _anthropic = anthropic
        
        config = get_ai_config()
        if not config.claude_api_key:
            logger.info("Claude API key not found - Claude provider will be unavailable")
            _anthropic_available = False
            return False
        
        _anthropic_available = True
        logger.info("Anthropic library loaded successfully")
        return True
        
    except ImportError:
        logger.info("anthropic package not installed. "
                   "Install with: pip install anthropic")
        _anthropic_available = False
        return False
    except Exception as e:
        logger.error(f"Failed to initialize Anthropic: {e}")
        _anthropic_available = False
        return False


class ClaudeProvider(AIProvider):
    """
    Anthropic Claude AI provider implementation.
    
    Claude is preferred for:
    - Complex reasoning and analysis
    - Investment thesis evaluation
    - Pattern explanation
    - Decision review
    
    Features:
    - Centralized configuration
    - System prompts support
    - JSON generation
    - Investment-specific methods
    """

    # Default system prompt for investment context
    DEFAULT_SYSTEM_PROMPT = (
        "You are an expert investment research assistant with deep knowledge of "
        "financial analysis, valuation methods, and behavioral finance. "
        "Provide thoughtful, balanced analysis while being direct and actionable."
    )

    def __init__(self, model: Optional[AIModel] = None):
        """
        Initialize Claude provider.

        Args:
            model: AIModel to use (defaults to CLAUDE_SONNET)
        """
        self._config = get_ai_config()
        
        # Ensure Anthropic is initialized
        _initialize_anthropic()
        
        # Set model
        if model is not None:
            if model.provider != AIProviderEnum.CLAUDE:
                raise ValueError(f"Model {model.model_id} is not a Claude model")
            self._model_enum = model
        else:
            self._model_enum = AIModel.CLAUDE_SONNET
        
        # Create client
        self._client = None
        if _anthropic_available and self._config.claude_api_key:
            try:
                self._client = _anthropic.Anthropic(api_key=self._config.claude_api_key)
                logger.debug(f"ClaudeProvider created with model: {self._model_enum.model_id}")
            except Exception as e:
                logger.error(f"Failed to create Claude client: {e}")

    @property
    def model_name(self) -> str:
        """Get current model name"""
        return self._model_enum.model_id

    def is_available(self) -> bool:
        """Check if Claude provider is available"""
        return _anthropic_available and self._client is not None

    def generate_text(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
        system: Optional[str] = None,
        system_prompt: Optional[str] = None,  # Backward compatibility
        prompt_name: Optional[str] = None,
        prompt_version: str = "1.0",
        **kwargs
    ) -> str:
        """
        Generate text completion using Claude.

        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-2.0)
            top_p: Nucleus sampling threshold (0.0-1.0)
            top_k: Limits token selection pool
            stop_sequences: List of strings to stop generation
            system: System prompt for context (Claude-specific)
            system_prompt: Deprecated alias for 'system'
            prompt_name: Name of the prompt for analytics (optional)
            prompt_version: Version of the prompt (default: "1.0")
            **kwargs: Claude-specific parameters (thinking, etc.)

        Returns:
            Generated text response
        """
        if not self.is_available():
            raise RuntimeError(
                "Claude provider is not available. "
                "Check ANTHROPIC_API_KEY environment variable."
            )

        # Start timing
        start_time = now_utc()
        input_tokens = None
        output_tokens = None
        success = True
        error_message = None
        result_text = None

        try:
            # Build message creation params
            create_params = {
                "model": self._model_enum.model_id,
                "max_tokens": max_tokens or self._config.default_max_tokens,
                "messages": [{"role": "user", "content": prompt}]
            }

            # Add system prompt (prefer 'system' over 'system_prompt')
            sys_prompt = system or system_prompt or self.DEFAULT_SYSTEM_PROMPT
            create_params["system"] = sys_prompt

            # Log system context usage
            if system or system_prompt:
                logger.info(f"Claude: Using custom system prompt (length: {len(sys_prompt)} chars)")
                logger.debug(f"Claude system prompt: {sys_prompt[:200]}...")
            else:
                logger.debug(f"Claude: Using default system prompt")

            # Add optional parameters
            if temperature is not None:
                create_params["temperature"] = temperature
            else:
                create_params["temperature"] = self._config.default_temperature

            if top_p is not None:
                create_params["top_p"] = top_p
            if top_k is not None:
                create_params["top_k"] = top_k
            if stop_sequences is not None:
                create_params["stop_sequences"] = stop_sequences

            message = self._client.messages.create(**create_params)

            # Extract token usage from response
            if hasattr(message, 'usage'):
                input_tokens = getattr(message.usage, 'input_tokens', None)
                output_tokens = getattr(message.usage, 'output_tokens', None)

            # Extract text from response
            if message.content and len(message.content) > 0:
                result_text = message.content[0].text
            else:
                raise ValueError("Empty response from Claude")

            return result_text

        except Exception as e:
            success = False
            error_message = str(e)
            logger.error(f"Claude generate_text error: {error_message}")
            raise

        finally:
            # Calculate latency in milliseconds
            end_time = now_utc()
            latency_ms = int((end_time - start_time).total_seconds() * 1000)

            # Log analytics (only if prompt_name provided)
            if prompt_name:
                log_prompt_usage(
                    prompt_name=prompt_name,
                    prompt_version=prompt_version,
                    provider="claude",
                    model=self._model_enum.model_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    success=success,
                    error_message=error_message
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
        Generate structured JSON response.

        Adds JSON instruction to prompt for reliable output.

        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-2.0)
            top_p: Nucleus sampling threshold (0.0-1.0)
            top_k: Limits token selection pool
            prompt_name: Name of the prompt for analytics (optional)
            prompt_version: Version of the prompt (default: "1.0")
            **kwargs: Additional parameters (system, etc.)

        Returns:
            Parsed JSON dictionary
        """
        if not self.is_available():
            raise RuntimeError("Claude provider is not available")

        # Add JSON instruction
        json_prompt = f"""{prompt}

IMPORTANT: Respond ONLY with valid JSON. No markdown code blocks, no explanation before or after, just the raw JSON object."""

        try:
            response_text = self.generate_text(
                json_prompt,
                max_tokens=max_tokens or self._config.default_max_tokens,
                temperature=temperature if temperature is not None else 0.3,  # Lower temp for JSON
                top_p=top_p,
                top_k=top_k,
                system=kwargs.get('system', "You are a helpful assistant that responds only with valid JSON."),
                prompt_name=prompt_name,
                prompt_version=prompt_version
            )

            # Clean up response
            text = response_text.strip()

            # Remove markdown code blocks if present
            if text.startswith('```json'):
                text = text[7:]
            elif text.startswith('```'):
                text = text[3:]
            if text.endswith('```'):
                text = text[:-3]

            return json.loads(text.strip())

        except json.JSONDecodeError as e:
            logger.error(f"Claude JSON parse error: {e}")
            logger.error(f"Raw response: {response_text[:500] if response_text else 'None'}")
            raise ValueError(f"Failed to parse JSON response: {e}")
        except Exception as e:
            logger.error(f"Claude generate_json error: {e}")
            raise

    def generate_embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        """
        Generate embeddings for texts.

        Claude doesn't have native embeddings, so we use sentence-transformers
        as a fallback.

        Args:
            texts: List of text strings to embed
            **kwargs: Additional parameters (model_name, etc.)

        Returns:
            List of embedding vectors
        """
        try:
            from sentence_transformers import SentenceTransformer

            # Allow custom model via kwargs
            model_name = kwargs.get('model', 'all-MiniLM-L6-v2')

            if not hasattr(self, '_embedding_model'):
                self._embedding_model = SentenceTransformer(model_name)
                logger.info(f"Loaded sentence-transformers ({model_name}) for Claude embeddings fallback")

            return [self._embedding_model.encode(text).tolist() for text in texts]

        except ImportError:
            raise NotImplementedError(
                "Claude doesn't support native embeddings. "
                "Install sentence-transformers for fallback: pip install sentence-transformers"
            )

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for Claude.
        
        Claude uses ~4 characters per token for English.
        """
        # Claude tokenization is roughly 4 chars per token
        return len(text) // 4

    # ============================================================
    # Investment-Specific Methods
    # ============================================================

    def analyze_thesis(
        self,
        company_name: str,
        thesis_text: str,
        research_data: Dict[str, Any],
        historical_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Analyze investment thesis quality.
        
        Claude excels at this type of nuanced reasoning task.

        Args:
            company_name: Name of the company
            thesis_text: The investment thesis to analyze
            research_data: Research metrics and findings
            historical_context: User's past mistakes and patterns

        Returns:
            Dict with analysis results:
            - quality_assessment: str
            - strengths: List[str]
            - weaknesses: List[str]
            - blind_spots: List[str]
            - suggested_questions: List[str]
            - confidence_adjustment: int (-2 to +2)
            - risk_flags: List[str]
        """
        history_section = ""
        if historical_context:
            history_section = f"""
USER'S HISTORICAL CONTEXT:
- Similar companies researched: {historical_context.get('similar_companies', 'None')}
- Past mistakes in this sector: {historical_context.get('sector_mistakes', 'None')}
- Common blind spots: {historical_context.get('blind_spots', 'None')}
"""
        
        # Build context info for YAML template
        context_info = f"""Company: {company_name}
Research Data:
- Questions answered: {research_data.get('questions_answered', 0)}/{research_data.get('questions_total', 0)}
- Documents analyzed: {research_data.get('documents_analyzed', 0)}
- Key findings: {research_data.get('key_findings', 'Not provided')}
- Identified risks: {research_data.get('identified_risks', 'Not provided')}
{history_section}"""

        # Use YAML prompt template
        prompt = get_intelligence_prompt(
            'thesis_analysis_simple',
            context_info=context_info,
            thesis_text=thesis_text
        )

        return self.generate_json(
            prompt,
            prompt_name='thesis_analysis_simple',
            prompt_version='1.0',
            temperature=0.5
        )

    def generate_warning(
        self,
        warning_context: Dict[str, Any],
        user_patterns: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate contextual investment warning.

        Creates helpful, non-judgmental warnings based on detected patterns.

        Args:
            warning_context: Current situation details
            user_patterns: Historical patterns from user's data

        Returns:
            Dict with warning details:
            - title: str
            - warning_text: str
            - severity: str (low/medium/high)
            - evidence: List[str]
            - suggested_action: str
            - related_past_mistakes: List[str]
        """
        # Use YAML prompt template
        prompt = get_intelligence_prompt(
            'warning_generation',
            situation_description=warning_context.get('situation_description', ''),
            company_name=warning_context.get('company_name', 'Unknown'),
            action=warning_context.get('action', 'Unknown'),
            pattern_description=warning_context.get('pattern_description', ''),
            similar_situations=user_patterns.get('similar_situations', 'None recorded'),
            outcomes=user_patterns.get('outcomes', 'Unknown'),
            common_mistakes=user_patterns.get('common_mistakes', 'None recorded')
        )

        return self.generate_json(
            prompt,
            prompt_name='warning_generation',
            prompt_version='1.0',
            temperature=0.5
        )

    def explain_pattern(
        self,
        pattern_type: str,
        pattern_data: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> str:
        """
        Generate human-friendly explanation of behavioral pattern.

        Creates supportive, educational explanations of detected patterns.

        Args:
            pattern_type: Type of pattern (e.g., 'disposition_effect')
            pattern_data: Data supporting the pattern
            user_context: Context about the user

        Returns:
            Plain English explanation (2-3 paragraphs)
        """
        # Use YAML prompt template
        prompt = get_intelligence_prompt(
            'pattern_explanation',
            pattern_type=pattern_type,
            pattern_data=json.dumps(pattern_data, indent=2),
            user_context=json.dumps(user_context, indent=2)
        )

        return self.generate_text(
            prompt,
            max_tokens=500,
            temperature=0.7,
            prompt_name='pattern_explanation',
            prompt_version='1.0'
        )

    def review_decision(
        self,
        decision_data: Dict[str, Any],
        thesis: str,
        outcome: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Review an investment decision for learning purposes.

        Args:
            decision_data: Details of the decision
            thesis: The investment thesis
            outcome: Actual outcome if known

        Returns:
            Dict with review insights
        """
        # Build outcome section if available
        outcome_section = ""
        if outcome:
            outcome_section = f"""
ACTUAL OUTCOME:
- Return: {outcome.get('return_pct', 'Unknown')}%
- Hold period: {outcome.get('hold_days', 'Unknown')} days
- Thesis accuracy: {outcome.get('thesis_accuracy', 'Unknown')}%
"""

        # Use YAML prompt template
        prompt = get_intelligence_prompt(
            'decision_review',
            company_name=decision_data.get('company_name', 'Unknown'),
            decision_date=decision_data.get('decision_date', 'Unknown'),
            action=decision_data.get('action', 'Unknown'),
            confidence_score=decision_data.get('confidence', 'Unknown'),
            thesis=thesis,
            research_time=decision_data.get('research_time', 'Unknown'),
            questions_answered=decision_data.get('questions_answered', 'Unknown'),
            documents_analyzed=decision_data.get('documents_analyzed', 'Unknown'),
            outcome_section=outcome_section
        )

        return self.generate_json(
            prompt,
            prompt_name='decision_review',
            prompt_version='1.0',
            temperature=0.5
        )
