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
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Generate text completion using Claude.

        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            system_prompt: System prompt for context (optional)
            **kwargs: Additional parameters

        Returns:
            Generated text response
        """
        if not self.is_available():
            raise RuntimeError(
                "Claude provider is not available. "
                "Check ANTHROPIC_API_KEY environment variable."
            )

        try:
            message = self._client.messages.create(
                model=self._model_enum.model_id,
                max_tokens=max_tokens or self._config.default_max_tokens,
                temperature=temperature if temperature is not None else self._config.default_temperature,
                system=system_prompt or self.DEFAULT_SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Extract text from response
            if message.content and len(message.content) > 0:
                return message.content[0].text
            
            raise ValueError("Empty response from Claude")

        except Exception as e:
            logger.error(f"Claude generate_text error: {str(e)}")
            raise

    def generate_json(
        self,
        prompt: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate structured JSON response.

        Adds JSON instruction to prompt for reliable output.

        Args:
            prompt: The input prompt
            **kwargs: Additional parameters

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
                max_tokens=kwargs.get('max_tokens', self._config.default_max_tokens),
                temperature=kwargs.get('temperature', 0.3),  # Lower temp for JSON
                system_prompt=kwargs.get('system_prompt', 
                    "You are a helpful assistant that responds only with valid JSON.")
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

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for texts.
        
        Claude doesn't have native embeddings, so we use sentence-transformers
        as a fallback.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        try:
            from sentence_transformers import SentenceTransformer
            
            if not hasattr(self, '_embedding_model'):
                self._embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("Loaded sentence-transformers for Claude embeddings fallback")
            
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
        
        prompt = f"""Analyze this investment thesis for {company_name}:

INVESTMENT THESIS:
{thesis_text}

RESEARCH DATA:
- Questions answered: {research_data.get('questions_answered', 0)}/{research_data.get('questions_total', 0)}
- Documents analyzed: {research_data.get('documents_analyzed', 0)}
- Key findings: {research_data.get('key_findings', 'Not provided')}
- Identified risks: {research_data.get('identified_risks', 'Not provided')}
{history_section}

Provide your analysis as JSON with these fields:
- quality_assessment: Brief overall assessment (2-3 sentences)
- strengths: List of 2-4 well-reasoned aspects
- weaknesses: List of 2-4 logical gaps or unsupported assumptions
- blind_spots: List of 2-3 factors the investor might be missing
- suggested_questions: List of 3-5 additional research questions
- confidence_adjustment: Integer from -2 (significantly reduce confidence) to +2 (can increase)
- risk_flags: List of any red flags warranting serious attention"""

        return self.generate_json(prompt, temperature=0.5)

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
        prompt = f"""You are a thoughtful investment advisor helping an investor avoid repeating past mistakes.

CURRENT SITUATION:
{warning_context.get('situation_description', '')}
Company: {warning_context.get('company_name', 'Unknown')}
Action being considered: {warning_context.get('action', 'Unknown')}

DETECTED PATTERN:
{warning_context.get('pattern_description', '')}

USER'S HISTORICAL PATTERNS:
- Past similar situations: {user_patterns.get('similar_situations', 'None recorded')}
- Outcomes in similar cases: {user_patterns.get('outcomes', 'Unknown')}
- Common mistakes: {user_patterns.get('common_mistakes', 'None recorded')}

Generate a helpful, non-judgmental warning as JSON with:
- title: Clear, concise title
- warning_text: Explanation of the concern (2-3 sentences)
- severity: "low", "medium", or "high"
- evidence: List of specific evidence points
- suggested_action: One concrete action to take
- related_past_mistakes: List of relevant past mistakes"""

        return self.generate_json(prompt, temperature=0.5)

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
        prompt = f"""You are a behavioral finance expert helping an investor understand their patterns.

DETECTED PATTERN: {pattern_type}

PATTERN DATA:
{json.dumps(pattern_data, indent=2)}

USER CONTEXT:
- Investment experience: {user_context.get('experience_level', 'Unknown')}
- Time on platform: {user_context.get('time_on_platform', 'Unknown')}
- Investment style: {user_context.get('investment_style', 'Unknown')}

Write a brief (2-3 paragraph), friendly explanation that:
1. Explains what this pattern means in plain English
2. Why it matters for investment performance
3. One specific thing they could try differently

Be supportive, not critical. Use "we" language to feel collaborative.
Do NOT use bullet points - write in natural paragraphs."""

        return self.generate_text(
            prompt,
            max_tokens=500,
            temperature=0.7,
            system_prompt="You are a supportive behavioral finance coach who explains concepts simply and encouragingly."
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
        outcome_section = ""
        if outcome:
            outcome_section = f"""
ACTUAL OUTCOME:
- Return: {outcome.get('return_pct', 'Unknown')}%
- Hold period: {outcome.get('hold_days', 'Unknown')} days
- Thesis accuracy: {outcome.get('thesis_accuracy', 'Unknown')}%
"""

        prompt = f"""Review this investment decision for learning purposes:

DECISION DETAILS:
- Company: {decision_data.get('company_name', 'Unknown')}
- Date: {decision_data.get('decision_date', 'Unknown')}
- Action: {decision_data.get('action', 'Unknown')}
- Confidence: {decision_data.get('confidence', 'Unknown')}/10

INVESTMENT THESIS:
{thesis}
{outcome_section}

Provide review as JSON with:
- process_quality: Rating 1-10 of decision process
- thesis_clarity: Rating 1-10 of thesis clarity
- key_learnings: List of 2-3 key learnings
- what_worked: List of things done well
- improvements: List of suggested improvements
- bias_indicators: Any cognitive biases detected"""

        return self.generate_json(prompt, temperature=0.5)
