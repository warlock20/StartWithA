"""
AI Configuration - Single source of truth for all AI settings

This module provides centralized configuration for all AI providers and models.
Change models globally via environment variables without editing code.

Usage:
    from app.services.ai.config import get_ai_config, AIProvider, AIModel, AITaskType
    
    config = get_ai_config()
    
    # Check provider availability
    if config.is_provider_available(AIProvider.CLAUDE):
        # Use Claude for quality tasks
        
    # Get best model for a task
    model = config.get_model_for_task(AITaskType.THESIS_ANALYSIS)

Environment Variables:
    GEMINI_API_KEY      - Google Gemini API key
    ANTHROPIC_API_KEY   - Anthropic Claude API key  
    OPENAI_API_KEY      - OpenAI API key (optional)
    
    AI_DEFAULT_MODEL    - Default model (default: gemini-2.5-flash)
    AI_QUALITY_MODEL    - Model for quality tasks (default: gemini-2.5-pro)
    AI_FAST_MODEL       - Model for fast tasks (default: gemini-2.5-flash)
    AI_PREFER_CLAUDE    - Use Claude for reasoning tasks (default: true)
"""

import os
import logging
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class AIProvider(Enum):
    """Available AI providers"""
    GEMINI = "gemini"
    CLAUDE = "claude"
    OPENAI = "openai"


class AIModel(Enum):
    """
    Available AI models with their provider mapping.
    
    Each model is a tuple of (model_id, provider).
    Access via: model.model_id, model.provider
    """
    # Gemini models
    GEMINI_PRO = ("gemini-pro", AIProvider.GEMINI)                      # Legacy - avoid
    GEMINI_FLASH_20 = ("gemini-2.0-flash", AIProvider.GEMINI)           # Fast, good quality
    GEMINI_FLASH_25 = ("gemini-2.5-flash", AIProvider.GEMINI)           # Recommended default
    GEMINI_PRO_25 = ("gemini-2.5-pro", AIProvider.GEMINI)               # Best Gemini quality
    
    # Claude models  
    CLAUDE_HAIKU = ("claude-3-5-haiku-20241022", AIProvider.CLAUDE)     # Fast, cost-effective
    CLAUDE_SONNET = ("claude-sonnet-4-20250514", AIProvider.CLAUDE)       # Good balance
    CLAUDE_OPUS = ("claude-3-opus-20240229", AIProvider.CLAUDE)         # Best quality
    
    # OpenAI models (for future use)
    GPT4 = ("gpt-4", AIProvider.OPENAI)
    GPT4_TURBO = ("gpt-4-turbo", AIProvider.OPENAI)
    GPT4O = ("gpt-4o", AIProvider.OPENAI)
    GPT35_TURBO = ("gpt-3.5-turbo", AIProvider.OPENAI)
    
    def __init__(self, model_id: str, provider: AIProvider):
        self.model_id = model_id
        self.provider = provider
    
    @classmethod
    def from_string(cls, model_name: str) -> 'AIModel':
        """
        Parse model name string to AIModel enum.
        
        Args:
            model_name: Model identifier string
            
        Returns:
            Matching AIModel or default (GEMINI_FLASH_25)
        """
        model_map = {
            # Gemini
            'gemini-pro': cls.GEMINI_PRO,
            'gemini-2.0-flash': cls.GEMINI_FLASH_20,
            'gemini-2.5-flash': cls.GEMINI_FLASH_25,
            'gemini-2.5-pro': cls.GEMINI_PRO_25,
            # Claude
            'claude-haiku': cls.CLAUDE_HAIKU,
            'claude-3-5-haiku-20241022': cls.CLAUDE_HAIKU,
            'claude-sonnet': cls.CLAUDE_SONNET,
            'claude-sonnet-4-20250514': cls.CLAUDE_SONNET,
            'claude-opus': cls.CLAUDE_OPUS,
            'claude-3-opus-20240229': cls.CLAUDE_OPUS,
            # OpenAI
            'gpt-4': cls.GPT4,
            'gpt-4-turbo': cls.GPT4_TURBO,
            'gpt-4o': cls.GPT4O,
            'gpt-3.5-turbo': cls.GPT35_TURBO,
        }
        
        result = model_map.get(model_name.lower())
        if result is None:
            logger.warning(f"Unknown model '{model_name}', using default GEMINI_FLASH_25")
            return cls.GEMINI_FLASH_25
        return result


class AITaskType(Enum):
    """
    Task types for intelligent provider/model routing.
    
    The AI service uses these to automatically select the best
    provider and model for each type of task.
    """
    # High-quality reasoning tasks -> Claude preferred
    THESIS_ANALYSIS = "thesis_analysis"
    PATTERN_EXPLANATION = "pattern_explanation"
    DECISION_REVIEW = "decision_review"
    INSIGHT_GENERATION = "insight_generation"
    WARNING_GENERATION = "warning_generation"
    
    # Cost-effective tasks -> Gemini preferred
    DOCUMENT_QA = "document_qa"
    SUMMARIZATION = "summarization"
    TEXT_EXTRACTION = "text_extraction"
    EMBEDDING_GENERATION = "embedding_generation"
    
    # General tasks -> Use default model
    GENERAL = "general"
    CHECKLIST_ANALYSIS = "checklist_analysis"
    JOURNAL_ANALYSIS = "journal_analysis"
    SECTOR_ANALYSIS = "sector_analysis"


# Task categories for routing decisions
QUALITY_TASKS = {
    AITaskType.THESIS_ANALYSIS,
    AITaskType.PATTERN_EXPLANATION,
    AITaskType.DECISION_REVIEW,
    AITaskType.INSIGHT_GENERATION,
    AITaskType.WARNING_GENERATION,
}

FAST_TASKS = {
    AITaskType.DOCUMENT_QA,
    AITaskType.SUMMARIZATION,
    AITaskType.TEXT_EXTRACTION,
    AITaskType.EMBEDDING_GENERATION,
}


@dataclass
class AIConfig:
    """
    AI configuration with environment variable support.
    
    This class holds all AI-related configuration and provides
    intelligent model selection based on task type.
    """
    
    # API Keys
    gemini_api_key: Optional[str] = None
    claude_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    
    # Model configuration
    default_model: AIModel = AIModel.GEMINI_FLASH_25
    quality_model: AIModel = AIModel.GEMINI_PRO_25
    fast_model: AIModel = AIModel.GEMINI_FLASH_25
    
    # Default generation parameters
    default_temperature: float = 0.7
    default_max_tokens: int = 2000
    
    # Routing preferences
    prefer_claude_for_reasoning: bool = True
    
    # Timeout settings (seconds)
    default_timeout: int = 180
    fast_timeout: int = 60
    
    @classmethod
    def from_env(cls) -> 'AIConfig':
        """
        Load configuration from environment variables.
        
        Returns:
            AIConfig instance populated from environment
        """
        config = cls()
        
        # Load API Keys
        config.gemini_api_key = os.getenv('GEMINI_API_KEY')
        config.claude_api_key = os.getenv('ANTHROPIC_API_KEY')
        config.openai_api_key = os.getenv('OPENAI_API_KEY')
        
        # Load model preferences from environment
        default_model_name = os.getenv('AI_DEFAULT_MODEL', 'gemini-2.5-flash')
        config.default_model = AIModel.from_string(default_model_name)
        
        quality_model_name = os.getenv('AI_QUALITY_MODEL', 'gemini-2.5-pro')
        config.quality_model = AIModel.from_string(quality_model_name)
        
        fast_model_name = os.getenv('AI_FAST_MODEL', 'gemini-2.5-flash')
        config.fast_model = AIModel.from_string(fast_model_name)
        
        # Load routing preferences
        config.prefer_claude_for_reasoning = os.getenv(
            'AI_PREFER_CLAUDE', 'true'
        ).lower() in ('true', '1', 'yes')
        
        # Load generation parameters
        try:
            config.default_temperature = float(os.getenv('AI_DEFAULT_TEMPERATURE', '0.7'))
        except ValueError:
            config.default_temperature = 0.7
            
        try:
            config.default_max_tokens = int(os.getenv('AI_DEFAULT_MAX_TOKENS', '2000'))
        except ValueError:
            config.default_max_tokens = 2000
        
        # Log configuration
        logger.info(f"AI Config loaded: default={config.default_model.model_id}, "
                   f"quality={config.quality_model.model_id}, "
                   f"gemini={'✓' if config.gemini_api_key else '✗'}, "
                   f"claude={'✓' if config.claude_api_key else '✗'}")
        
        return config
    
    def is_provider_available(self, provider: AIProvider) -> bool:
        """
        Check if a provider is configured with an API key.
        
        Args:
            provider: The AIProvider to check
            
        Returns:
            True if the provider has an API key configured
        """
        if provider == AIProvider.GEMINI:
            return bool(self.gemini_api_key)
        elif provider == AIProvider.CLAUDE:
            return bool(self.claude_api_key)
        elif provider == AIProvider.OPENAI:
            return bool(self.openai_api_key)
        return False
    
    def get_available_providers(self) -> list[AIProvider]:
        """
        Get list of all available (configured) providers.
        
        Returns:
            List of AIProvider enums that have API keys
        """
        available = []
        for provider in AIProvider:
            if self.is_provider_available(provider):
                available.append(provider)
        return available
    
    def get_model_for_task(self, task: AITaskType) -> AIModel:
        """
        Get the best model for a given task type.
        
        Implements intelligent routing:
        - Quality tasks -> Claude (if available) or quality_model
        - Fast tasks -> fast_model
        - General tasks -> default_model
        
        Args:
            task: The type of task to perform
            
        Returns:
            Best AIModel for the task
        """
        # Quality tasks - prefer Claude for reasoning
        if task in QUALITY_TASKS:
            if self.prefer_claude_for_reasoning and self.claude_api_key:
                return AIModel.CLAUDE_SONNET
            return self.quality_model
        
        # Fast tasks - use fast model
        if task in FAST_TASKS:
            return self.fast_model
        
        # Default for other tasks
        return self.default_model
    
    def get_provider_for_task(self, task: AITaskType) -> AIProvider:
        """
        Get the provider for a task based on model selection.
        
        Args:
            task: The type of task
            
        Returns:
            AIProvider that should handle this task
        """
        model = self.get_model_for_task(task)
        return model.provider


# ============================================================
# Singleton Configuration Instance
# ============================================================

_config: Optional[AIConfig] = None


def get_ai_config() -> AIConfig:
    """
    Get the singleton AI configuration instance.
    
    Creates the instance on first call, returns cached instance after.
    
    Returns:
        AIConfig singleton instance
    """
    global _config
    if _config is None:
        _config = AIConfig.from_env()
    return _config


def reload_ai_config() -> AIConfig:
    """
    Reload configuration from environment.
    
    Useful for testing or when environment variables change.
    
    Returns:
        New AIConfig instance
    """
    global _config
    _config = AIConfig.from_env()
    return _config


def reset_ai_config():
    """
    Reset configuration to None.
    
    Primarily used for testing.
    """
    global _config
    _config = None
