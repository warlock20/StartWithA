"""
AI Research Assistant Service

Provides AI-powered research assistance with three modes:
1. Challenge - Counter-arguments to test reasoning
2. Elaboration - Follow-up questions to deepen analysis
3. Fact-Check - Verify claims and request sources

This service is modular and can be used across:
- Research checklists
- Decision journal
- Portfolio notes
- Any feature with user-generated text + context

Usage:
    from app.services.ai_research_assistant import ai_research_assistant

    # Challenge mode
    response = ai_research_assistant.generate_challenge(
        question_text="What is the company's moat?",
        user_answer="Network effects from 2-sided marketplace",
        context_data={'company_name': 'Shopify'}
    )

    # Elaboration mode
    response = ai_research_assistant.generate_elaboration(
        question_text="What are the key risks?",
        user_answer="Regulatory risk in EU markets",
        context_data={'company_name': 'Meta'}
    )

    # Fact-check mode
    response = ai_research_assistant.generate_factcheck(
        question_text="What is the revenue growth?",
        user_answer="Revenue grew 40% YoY to $2B",
        context_data={'company_name': 'Snowflake'}
    )
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from app.services.ai import ai_service
from app.services.ai.prompt_service import prompt_service
from app.services.ai.config import AIProvider, AIModel

logger = logging.getLogger(__name__)


# Constants
PROMPT_CATEGORY = "research"
MODE_CHALLENGE = "challenge"
MODE_ELABORATION = "elaboration"
MODE_FACTCHECK = "factcheck"

VALID_MODES = [MODE_CHALLENGE, MODE_ELABORATION, MODE_FACTCHECK]


@dataclass
class AIResearchResponse:
    """
    Structured response from AI Research Assistant.

    Attributes:
        success: Whether the operation succeeded
        mode: Which mode was used (challenge/elaboration/factcheck)
        response_text: The AI-generated response
        tokens_used: Approximate tokens used (for cost tracking)
        error: Error message if failed
        metadata: Additional metadata from prompt template
    """
    success: bool
    mode: str
    response_text: Optional[str] = None
    tokens_used: Optional[int] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'success': self.success,
            'mode': self.mode,
            'response': self.response_text,
            'tokens_used': self.tokens_used,
            'error': self.error,
            'metadata': self.metadata
        }


class AIResearchAssistant:
    """
    AI Research Assistant service for challenging and improving user research.

    Provides three core modes:
    - Challenge: Generate counter-arguments
    - Elaboration: Ask follow-up questions
    - Fact-Check: Verify claims and request sources

    This service is provider-agnostic and uses YAML prompt templates
    for easy tuning and maintenance.
    """

    def __init__(self):
        """Initialize AI Research Assistant."""
        self.prompt_service = prompt_service
        self.ai_service = ai_service

    def generate_challenge(
        self,
        question_text: str,
        user_answer: str,
        context_data: Dict[str, Any]
    ) -> AIResearchResponse:
        """
        Generate counter-arguments to challenge user's reasoning.

        Args:
            question_text: The research question being answered
            user_answer: User's answer to the question
            context_data: Additional context (must include 'company_name')

        Returns:
            AIResearchResponse with counter-arguments and critical questions

        Example:
            response = assistant.generate_challenge(
                question_text="What is the company's moat?",
                user_answer="Network effects from 2-sided marketplace",
                context_data={'company_name': 'Shopify'}
            )
            print(response.response_text)
        """
        return self._generate_response(
            mode=MODE_CHALLENGE,
            question_text=question_text,
            user_answer=user_answer,
            context_data=context_data
        )

    def generate_elaboration(
        self,
        question_text: str,
        user_answer: str,
        context_data: Dict[str, Any]
    ) -> AIResearchResponse:
        """
        Generate follow-up questions to deepen analysis.

        Args:
            question_text: The research question being answered
            user_answer: User's answer to the question
            context_data: Additional context (must include 'company_name')

        Returns:
            AIResearchResponse with follow-up questions

        Example:
            response = assistant.generate_elaboration(
                question_text="How does the company monetize?",
                user_answer="Transaction fees (3% of GMV)",
                context_data={'company_name': 'Stripe'}
            )
        """
        return self._generate_response(
            mode=MODE_ELABORATION,
            question_text=question_text,
            user_answer=user_answer,
            context_data=context_data
        )

    def generate_factcheck(
        self,
        question_text: str,
        user_answer: str,
        context_data: Dict[str, Any]
    ) -> AIResearchResponse:
        """
        Identify claims requiring verification and request sources.

        Args:
            question_text: The research question being answered
            user_answer: User's answer to the question
            context_data: Additional context (must include 'company_name')

        Returns:
            AIResearchResponse with claims requiring verification

        Example:
            response = assistant.generate_factcheck(
                question_text="What is the growth rate?",
                user_answer="Revenue grew 40% YoY to $2B",
                context_data={'company_name': 'Snowflake'}
            )
        """
        return self._generate_response(
            mode=MODE_FACTCHECK,
            question_text=question_text,
            user_answer=user_answer,
            context_data=context_data
        )

    def _generate_response(
        self,
        mode: str,
        question_text: str,
        user_answer: str,
        context_data: Dict[str, Any]
    ) -> AIResearchResponse:
        """
        Internal method to generate AI response for any mode.

        Args:
            mode: challenge | elaboration | factcheck
            question_text: The research question
            user_answer: User's answer
            context_data: Context including company_name

        Returns:
            AIResearchResponse object
        """
        # Validate inputs
        if mode not in VALID_MODES:
            return AIResearchResponse(
                success=False,
                mode=mode,
                error=f"Invalid mode '{mode}'. Valid modes: {VALID_MODES}"
            )

        if not question_text or not question_text.strip():
            return AIResearchResponse(
                success=False,
                mode=mode,
                error="question_text is required"
            )

        if not user_answer or not user_answer.strip():
            return AIResearchResponse(
                success=False,
                mode=mode,
                error="user_answer is required"
            )

        if 'company_name' not in context_data:
            return AIResearchResponse(
                success=False,
                mode=mode,
                error="context_data must include 'company_name'"
            )

        # Map mode to prompt template name
        prompt_name = f"{mode}_mode"

        try:
            # Load prompt template with metadata
            prompt_data = self.prompt_service.get_prompt_with_metadata(
                category=PROMPT_CATEGORY,
                name=prompt_name,
                question_text=question_text,
                user_answer=user_answer,
                **context_data
            )

            prompt_text = prompt_data['prompt']
            metadata = prompt_data['metadata']

            # Convert provider and model from strings to enums
            provider_str = metadata.get('preferred_provider')
            model_str = metadata.get('model')

            provider_enum = None
            model_enum = None

            if provider_str:
                try:
                    provider_enum = AIProvider(provider_str)
                except ValueError:
                    logger.warning(f"Invalid provider '{provider_str}', using default")

            if model_str:
                model_enum = AIModel.from_string(model_str)

            logger.info(
                f"Generating {mode} response for question: {question_text[:50]}... "
                f"(company: {context_data.get('company_name')}), "
                f"provider: {provider_str}, model: {model_str}"
            )

            # Call AI service with prompt template configuration from YAML
            ai_response = self.ai_service.generate_text(
                prompt=prompt_text,
                max_tokens=metadata.get('max_tokens', 500),
                temperature=metadata.get('temperature', 0.7),
                provider=provider_enum,
                model=model_enum,
            )

            # Estimate tokens (rough approximation: 1 token ≈ 4 characters)
            tokens_estimate = len(ai_response) // 4

            logger.info(
                f"{mode.capitalize()} mode completed successfully. "
                f"Response length: {len(ai_response)} chars (~{tokens_estimate} tokens)"
            )

            return AIResearchResponse(
                success=True,
                mode=mode,
                response_text=ai_response.strip(),
                tokens_used=tokens_estimate,
                metadata={
                    'template_version': metadata.get('version'),
                    'template_name': prompt_name,
                    'category': PROMPT_CATEGORY,
                    'question_length': len(question_text),
                    'answer_length': len(user_answer),
                    'provider': provider_str or 'gemini',
                    'model': model_str or 'gemini-flash',
                }
            )

        except ValueError as e:
            # Prompt template errors (missing category, name, or variables)
            logger.error(f"Prompt template error for {mode}: {e}")
            return AIResearchResponse(
                success=False,
                mode=mode,
                error=f"Prompt configuration error: {str(e)}"
            )

        except Exception as e:
            # AI service errors or unexpected errors
            logger.error(f"AI Research Assistant error ({mode}): {e}", exc_info=True)
            return AIResearchResponse(
                success=False,
                mode=mode,
                error=f"Failed to generate response: {str(e)}"
            )

    def validate_context(self, context_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate that context_data has required fields.

        Args:
            context_data: Context dictionary to validate

        Returns:
            Tuple of (is_valid, error_message)

        Example:
            is_valid, error = assistant.validate_context({'company_name': 'Apple'})
            if not is_valid:
                print(f"Invalid context: {error}")
        """
        if not isinstance(context_data, dict):
            return False, "context_data must be a dictionary"

        if 'company_name' not in context_data:
            return False, "context_data must include 'company_name'"

        if not context_data['company_name'] or not context_data['company_name'].strip():
            return False, "'company_name' cannot be empty"

        return True, None

    def get_available_modes(self) -> list[str]:
        """
        Get list of available AI assistance modes.

        Returns:
            List of mode names
        """
        return VALID_MODES.copy()

    def get_mode_info(self, mode: str) -> Dict[str, Any]:
        """
        Get information about a specific mode.

        Args:
            mode: Mode name (challenge/elaboration/factcheck)

        Returns:
            Dict with mode metadata

        Raises:
            ValueError: If mode is invalid
        """
        if mode not in VALID_MODES:
            raise ValueError(f"Invalid mode '{mode}'. Valid modes: {VALID_MODES}")

        prompt_name = f"{mode}_mode"

        try:
            info = self.prompt_service.get_prompt_info(
                category=PROMPT_CATEGORY,
                name=prompt_name
            )
            return {
                'mode': mode,
                'name': info.get('name', mode),
                'description': info.get('description', ''),
                'version': info.get('version', '1.0'),
                'max_tokens': info.get('max_tokens', 500),
                'temperature': info.get('temperature', 0.7),
                'required_variables': info.get('required_variables', []),
            }
        except Exception as e:
            logger.error(f"Failed to get mode info for '{mode}': {e}")
            return {
                'mode': mode,
                'error': str(e)
            }


# Singleton instance for easy access
_ai_research_assistant = None


def get_ai_research_assistant() -> AIResearchAssistant:
    """
    Get singleton instance of AI Research Assistant.

    Returns:
        AIResearchAssistant instance
    """
    global _ai_research_assistant
    if _ai_research_assistant is None:
        _ai_research_assistant = AIResearchAssistant()
    return _ai_research_assistant


# Convenience instance for direct import
ai_research_assistant = get_ai_research_assistant()


# Convenience functions for quick access
def generate_challenge(question: str, answer: str, context: Dict[str, Any]) -> AIResearchResponse:
    """Quick access to challenge mode."""
    return ai_research_assistant.generate_challenge(question, answer, context)


def generate_elaboration(question: str, answer: str, context: Dict[str, Any]) -> AIResearchResponse:
    """Quick access to elaboration mode."""
    return ai_research_assistant.generate_elaboration(question, answer, context)


def generate_factcheck(question: str, answer: str, context: Dict[str, Any]) -> AIResearchResponse:
    """Quick access to fact-check mode."""
    return ai_research_assistant.generate_factcheck(question, answer, context)
