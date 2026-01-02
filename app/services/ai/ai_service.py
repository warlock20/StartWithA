"""
AI Service - Unified entry point for all AI operations

This is the main service that routes requests to optimal providers
based on task type, availability, and configuration.

Usage:
    from app.services.ai import ai_service
    
    # Simple text generation (uses default model)
    response = ai_service.generate("Analyze this company...")
    
    # Task-specific with auto-routing
    response = ai_service.generate(
        "Analyze this thesis...",
        task=AITaskType.THESIS_ANALYSIS
    )
    
    # Force specific provider
    response = ai_service.generate(
        "Quick summary...",
        provider=AIProvider.GEMINI
    )
    
    # Investment-specific methods
    analysis = ai_service.analyze_thesis(company, thesis, data)
    warning = ai_service.generate_warning(context, patterns)
    
    # Convenience functions
    from app.services.ai import generate, generate_json
    response = generate("Hello")
    data = generate_json("Return JSON with name and age")
"""

import logging
from typing import Dict, Any, List, Optional

from app.services.ai.prompt_service import get_intelligence_prompt
from .config import (
    get_ai_config,
    AIConfig,
    AIProvider,
    AIModel,
    AITaskType,
    QUALITY_TASKS,
    FAST_TASKS,
)
from .providers.base import AIProvider as AIProviderBase
from .providers.gemini import GeminiProvider
from .providers.claude import ClaudeProvider

logger = logging.getLogger(__name__)


class AIService:
    """
    Unified AI service that routes requests to optimal providers.
    
    This service:
    - Manages provider instances
    - Routes tasks to best available provider
    - Provides consistent interface across providers
    - Handles fallbacks when preferred provider unavailable
    
    Attributes:
        config: AIConfig instance
        providers: Dict of initialized providers
    """
    
    def __init__(self):
        """Initialize AI service with available providers."""
        self._config = get_ai_config()
        self._providers: Dict[AIProvider, AIProviderBase] = {}
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize all available providers."""
        # Initialize Gemini
        if self._config.is_provider_available(AIProvider.GEMINI):
            try:
                self._providers[AIProvider.GEMINI] = GeminiProvider()
                logger.info("Gemini provider initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini provider: {e}")
        
        # Initialize Claude
        if self._config.is_provider_available(AIProvider.CLAUDE):
            try:
                self._providers[AIProvider.CLAUDE] = ClaudeProvider()
                logger.info("Claude provider initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Claude provider: {e}")
        
        if not self._providers:
            logger.warning("No AI providers available! Check API keys.")
    
    def _get_provider(
        self,
        task: Optional[AITaskType] = None,
        provider: Optional[AIProvider] = None,
        model: Optional[AIModel] = None
    ) -> AIProviderBase:
        """
        Get the best available provider for the request.
        
        Priority:
        1. Explicitly requested provider
        2. Provider for explicitly requested model
        3. Best provider for task type
        4. First available provider
        
        Args:
            task: Task type for intelligent routing
            provider: Explicitly requested provider
            model: Explicitly requested model
            
        Returns:
            AIProviderBase instance
            
        Raises:
            RuntimeError: If no suitable provider available
        """
        # If specific provider requested
        if provider is not None:
            if provider in self._providers and self._providers[provider].is_available():
                return self._providers[provider]
            raise RuntimeError(f"Requested provider {provider.value} is not available")
        
        # If specific model requested
        if model is not None:
            provider_type = model.provider
            if provider_type in self._providers:
                # Create new provider instance with specific model
                if provider_type == AIProvider.GEMINI:
                    return GeminiProvider(model=model)
                elif provider_type == AIProvider.CLAUDE:
                    return ClaudeProvider(model=model)
            raise RuntimeError(f"Provider for model {model.model_id} is not available")
        
        # Route based on task type
        if task is not None:
            target_model = self._config.get_model_for_task(task)
            target_provider = target_model.provider
            
            if target_provider in self._providers and self._providers[target_provider].is_available():
                logger.debug(f"Routing task {task.value} to {target_provider.value}")
                return self._providers[target_provider]
            
            # Fallback to any available provider
            logger.warning(
                f"Preferred provider {target_provider.value} not available for {task.value}, "
                "falling back to available provider"
            )
        
        # Return first available provider
        for prov in self._providers.values():
            if prov.is_available():
                return prov
        
        raise RuntimeError("No AI providers available. Check API key configuration.")
    
    # ============================================================
    # Core Generation Methods
    # ============================================================
    
    def generate(
        self,
        prompt: str,
        task: Optional[AITaskType] = None,
        provider: Optional[AIProvider] = None,
        model: Optional[AIModel] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """
        Generate text response.
        
        This is the main method for text generation. It routes to the
        optimal provider based on task type or explicit parameters.
        
        Args:
            prompt: The input prompt
            task: Task type for intelligent routing
            provider: Force specific provider
            model: Force specific model
            max_tokens: Max tokens to generate
            temperature: Sampling temperature (0-1)
            **kwargs: Additional provider-specific params
        
        Returns:
            Generated text
            
        Examples:
            # Simple generation
            response = ai_service.generate("Explain value investing")
            
            # Task-specific (routes to best provider)
            response = ai_service.generate(
                "Analyze this thesis...",
                task=AITaskType.THESIS_ANALYSIS
            )
            
            # Force Gemini
            response = ai_service.generate(
                "Quick summary...",
                provider=AIProvider.GEMINI
            )
        """
        ai_provider = self._get_provider(task, provider, model)
        
        return ai_provider.generate_text(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
    
    def generate_json(
        self,
        prompt: str,
        task: Optional[AITaskType] = None,
        provider: Optional[AIProvider] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate structured JSON response.
        
        Args:
            prompt: The input prompt (should describe expected JSON structure)
            task: Task type for routing
            provider: Force specific provider
            **kwargs: Additional parameters
            
        Returns:
            Parsed JSON as dictionary
        """
        ai_provider = self._get_provider(task, provider)
        return ai_provider.generate_json(prompt, **kwargs)
    
    def generate_embeddings(
        self,
        texts: List[str],
        provider: Optional[AIProvider] = None
    ) -> List[List[float]]:
        """
        Generate embeddings for texts.
        
        Prefers Gemini for embeddings as it has native support.
        
        Args:
            texts: List of text strings to embed
            provider: Force specific provider
            
        Returns:
            List of embedding vectors
        """
        # Prefer Gemini for embeddings (native support)
        if provider is None and AIProvider.GEMINI in self._providers:
            provider = AIProvider.GEMINI
        
        ai_provider = self._get_provider(provider=provider)
        return ai_provider.generate_embeddings(texts)
    
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
        
        Routes to Claude if available (better reasoning), falls back to Gemini.
        
        Args:
            company_name: Name of the company
            thesis_text: The investment thesis
            research_data: Research metrics and findings
            historical_context: User's past patterns (optional)
            
        Returns:
            Dict with:
            - quality_assessment: str
            - strengths: List[str]
            - weaknesses: List[str]
            - blind_spots: List[str]
            - suggested_questions: List[str]
            - confidence_adjustment: int
            - risk_flags: List[str]
        """
        # Try Claude first (specialized method)
        if AIProvider.CLAUDE in self._providers:
            claude = self._providers[AIProvider.CLAUDE]
            if isinstance(claude, ClaudeProvider) and claude.is_available():
                return claude.analyze_thesis(
                    company_name, thesis_text, research_data, historical_context
                )
        
        # Fallback to Gemini with structured prompt
        prompt = self._build_thesis_prompt(
            company_name, thesis_text, research_data, historical_context
        )
        return self.generate_json(prompt, task=AITaskType.THESIS_ANALYSIS)
    
    def generate_warning(
        self,
        warning_context: Dict[str, Any],
        user_patterns: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate contextual investment warning.
        
        Args:
            warning_context: Current situation details
            user_patterns: Historical patterns from user's data
            
        Returns:
            Dict with:
            - title: str
            - warning_text: str
            - severity: str (low/medium/high)
            - evidence: List[str]
            - suggested_action: str
        """
        # Try Claude first
        if AIProvider.CLAUDE in self._providers:
            claude = self._providers[AIProvider.CLAUDE]
            if isinstance(claude, ClaudeProvider) and claude.is_available():
                return claude.generate_warning(warning_context, user_patterns)
        
        # Fallback to Gemini
        prompt = self._build_warning_prompt(warning_context, user_patterns)
        return self.generate_json(prompt, task=AITaskType.WARNING_GENERATION)
    
    def explain_pattern(
        self,
        pattern_type: str,
        pattern_data: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> str:
        """
        Explain behavioral pattern in plain English.
        
        Args:
            pattern_type: Type of pattern detected
            pattern_data: Data supporting the pattern
            user_context: Context about the user
            
        Returns:
            Plain English explanation
        """
        # Try Claude first
        if AIProvider.CLAUDE in self._providers:
            claude = self._providers[AIProvider.CLAUDE]
            if isinstance(claude, ClaudeProvider) and claude.is_available():
                return claude.explain_pattern(pattern_type, pattern_data, user_context)
        
        # Fallback - use YAML prompt
        prompt = get_intelligence_prompt(
            'pattern_explanation',
            pattern_type=pattern_type,
            pattern_data=str(pattern_data),
            user_context=str(user_context)
        )

        return self.generate(prompt, task=AITaskType.PATTERN_EXPLANATION)
    
    def answer_research_question(
        self,
        question: str,
        documents: List[str],
        company_context: Dict[str, Any]
    ) -> str:
        """
        Answer research question based on documents.
        
        Uses Gemini by default (cost-effective for document Q&A).
        
        Args:
            question: The research question
            documents: List of document texts
            company_context: Company information
            
        Returns:
            Answer based on documents
        """
        # Limit documents to avoid token limits
        doc_text = "\n\n---\n\n".join(documents[:3])

        # Use YAML prompt
        prompt = get_intelligence_prompt(
            'research_qa',
            company_name=company_context.get('company_name', 'Unknown'),
            sector=company_context.get('sector', 'Unknown'),
            documents_text=doc_text,
            question=question
        )

        return self.generate(prompt, task=AITaskType.DOCUMENT_QA)
    
    def summarize(
        self,
        text: str,
        max_length: Optional[int] = None,
        focus: str = "key_points"
    ) -> str:
        """
        Summarize text content.
        
        Args:
            text: Text to summarize
            max_length: Maximum words in summary
            focus: Focus area (key_points, risks, opportunities)
            
        Returns:
            Summary text
        """
        length_instruction = f"Keep summary under {max_length} words." if max_length else "No specific length requirement."

        # Use YAML prompt
        prompt = get_intelligence_prompt(
            'text_summarization',
            focus=focus,
            text_content=text,
            length_instruction=length_instruction
        )

        return self.generate(prompt, task=AITaskType.SUMMARIZATION)
    
    # ============================================================
    # Helper Methods
    # ============================================================
    
    def _build_thesis_prompt(
        self,
        company_name: str,
        thesis_text: str,
        research_data: Dict,
        historical_context: Optional[Dict]
    ) -> str:
        """Build thesis analysis prompt for Gemini fallback."""
        history_section = ""
        if historical_context:
            history_section = f"""
Historical Context:
- Similar companies: {historical_context.get('similar_companies', 'None')}
- Past mistakes: {historical_context.get('sector_mistakes', 'None')}
"""
        
        return f"""Analyze this investment thesis for {company_name}:

THESIS:
{thesis_text}

RESEARCH DATA:
{research_data}
{history_section}

Respond with JSON containing:
- quality_assessment: string (2-3 sentences)
- strengths: list of strings
- weaknesses: list of strings
- blind_spots: list of strings
- suggested_questions: list of strings
- confidence_adjustment: integer (-2 to +2)
- risk_flags: list of strings"""
    
    def _build_warning_prompt(
        self,
        context: Dict,
        patterns: Dict
    ) -> str:
        """Build warning generation prompt for Gemini fallback."""
        return f"""Generate an investment warning based on:

CURRENT SITUATION:
{context}

USER PATTERNS:
{patterns}

Respond with JSON containing:
- title: string
- warning_text: string
- severity: "low", "medium", or "high"
- evidence: list of strings
- suggested_action: string"""
    
    # ============================================================
    # Status and Utility Methods
    # ============================================================
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get status of all providers and configuration.
        
        Returns:
            Dict with status information
        """
        provider_status = {}
        for provider_type, provider in self._providers.items():
            provider_status[provider_type.value] = {
                'available': provider.is_available(),
                'model': provider.model_name
            }
        
        return {
            'available_providers': [p.value for p in self._providers.keys()],
            'provider_details': provider_status,
            'default_model': self._config.default_model.model_id,
            'quality_model': self._config.quality_model.model_id,
            'fast_model': self._config.fast_model.model_id,
            'prefer_claude_for_reasoning': self._config.prefer_claude_for_reasoning,
        }
    
    def is_available(self) -> bool:
        """Check if any AI provider is available."""
        return any(p.is_available() for p in self._providers.values())
    
    def get_available_providers(self) -> List[AIProvider]:
        """Get list of available providers."""
        return [k for k, v in self._providers.items() if v.is_available()]


# ============================================================
# Singleton Instance
# ============================================================

_ai_service: Optional[AIService] = None


def get_ai_service() -> AIService:
    """
    Get the singleton AI service instance.
    
    Returns:
        AIService singleton
    """
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service


def reset_ai_service():
    """
    Reset the AI service singleton.
    
    Useful for testing or reloading configuration.
    """
    global _ai_service
    _ai_service = None


# ============================================================
# Convenience Functions
# ============================================================

def generate(prompt: str, **kwargs) -> str:
    """
    Quick access to text generation.
    
    Args:
        prompt: Input prompt
        **kwargs: Additional parameters
        
    Returns:
        Generated text
    """
    return get_ai_service().generate(prompt, **kwargs)


def generate_json(prompt: str, **kwargs) -> Dict[str, Any]:
    """
    Quick access to JSON generation.
    
    Args:
        prompt: Input prompt
        **kwargs: Additional parameters
        
    Returns:
        Parsed JSON dictionary
    """
    return get_ai_service().generate_json(prompt, **kwargs)


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Quick access to embedding generation.
    
    Args:
        texts: List of texts to embed
        
    Returns:
        List of embedding vectors
    """
    return get_ai_service().generate_embeddings(texts)


def generate_ai_content(prompt: str, **kwargs) -> str:
    """
    Generate AI content.
    Backward-compatible function name from old llm_service.py.
    """
    return get_ai_service().generate(prompt, **kwargs)


async def generate_ai_content_async(prompt: str, **kwargs) -> str:
    """
    Generate AI content asynchronously.
    """
    return get_ai_service().generate(prompt, **kwargs)


def generate_ai_json(prompt: str, **kwargs) -> Dict[str, Any]:
    """
    Generate structured JSON response.
    Backward-compatible function name from old llm_service.py.
    """
    return get_ai_service().generate_json(prompt, **kwargs)

def get_available_providers() -> List[str]:
    ai = get_ai_service()
    return [p.value for p in ai.get_available_providers()]