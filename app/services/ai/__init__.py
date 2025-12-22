"""
AI Services Package - Centralized AI functionality

This package provides a unified interface for all AI operations across the platform.
It supports multiple providers (Gemini, Claude) with intelligent task-based routing.

Quick Start:
    from app.services.ai import ai_service, generate, generate_json
    
    # Simple text generation
    response = ai_service.generate("Analyze this company...")
    
    # Or use convenience function
    response = generate("Analyze this company...")
    
    # JSON generation
    data = generate_json("Return JSON with name and age fields")
    
    # Task-specific with auto-routing (uses best provider for task)
    from app.services.ai import AITaskType
    response = ai_service.generate(
        "Analyze this thesis...",
        task=AITaskType.THESIS_ANALYSIS
    )
    
    # Force specific provider
    from app.services.ai import AIProvider
    response = ai_service.generate(
        "Quick summary...",
        provider=AIProvider.GEMINI
    )

Investment-Specific Methods:
    # Thesis analysis (routes to Claude if available)
    analysis = ai_service.analyze_thesis(company, thesis, research_data)
    
    # Generate warnings based on patterns
    warning = ai_service.generate_warning(context, user_patterns)
    
    # Explain behavioral patterns
    explanation = ai_service.explain_pattern(pattern_type, data, context)
    
    # Answer research questions from documents
    answer = ai_service.answer_research_question(question, documents, context)

Configuration:
    Set these environment variables:
    
    GEMINI_API_KEY      - Google Gemini API key
    ANTHROPIC_API_KEY   - Anthropic Claude API key (optional, for quality tasks)
    
    AI_DEFAULT_MODEL    - Default model (default: gemini-2.5-flash)
    AI_QUALITY_MODEL    - Model for quality tasks (default: gemini-2.5-pro)
    AI_PREFER_CLAUDE    - Use Claude for reasoning tasks (default: true)

Module Structure:
    app/services/ai/
    ├── __init__.py         # This file - main exports
    ├── config.py           # Configuration and enums
    ├── ai_service.py       # Main AIService class
    └── providers/
        ├── base.py         # Abstract provider interface
        ├── gemini.py       # Gemini provider
        └── claude.py       # Claude provider
"""

# Configuration exports
from .config import (
    AIProvider,
    AIModel,
    AITaskType,
    AIConfig,
    get_ai_config,
    reload_ai_config,
)

# Service exports
from .ai_service import (
    AIService,
    get_ai_service,
    reset_ai_service,
    generate,
    generate_json,
    generate_embeddings,
    get_available_providers,
    # Backward-compatible names
    generate_ai_content,
    generate_ai_content_async,
    generate_ai_json,
)

# Provider exports (for advanced usage)
from .providers import (
    GeminiProvider,
    ClaudeProvider,
)

# Note: document_processor is NOT imported here to avoid circular imports
# Import directly: from app.services.ai.document_processor import ...

# Prompt service exports
from .prompt_service import (
    prompt_service,
    PromptService,
    get_kill_checklist_prompt,
    get_research_journal_prompt,
    get_research_template_prompt,
    get_sector_research_prompt,
    get_document_processing_prompt,
    get_competitor_analysis_prompt,
    list_all_prompts,
    test_prompt,
)

# Create singleton instance for easy access
ai_service = get_ai_service()

__all__ = [
    # Main service instance
    'ai_service',
    
    # Service class and factory
    'AIService',
    'get_ai_service',
    'reset_ai_service',
    
    # Convenience functions
    'generate',
    'generate_json',
    'generate_embeddings',
    # Backward-compatible names
    'generate_ai_content',
    'generate_ai_content_async',
    'generate_ai_json',
    
    # Configuration
    'AIProvider',
    'AIModel',
    'AITaskType',
    'AIConfig',
    'get_ai_config',
    'reload_ai_config',
    
    # Providers (for advanced usage)
    'GeminiProvider',
    'ClaudeProvider',
    
    # Prompt service
    'prompt_service',
    'PromptService',
    'get_kill_checklist_prompt',
    'get_research_journal_prompt',
    'get_research_template_prompt',
    'get_sector_research_prompt',
    'get_document_processing_prompt',
    'get_competitor_analysis_prompt',
    'list_all_prompts',
    'test_prompt',
]