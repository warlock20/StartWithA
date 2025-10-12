"""
AI Integration Module

This module provides AI-powered features for sector research:
- Text summarization
- Auto-categorization
- Tag suggestions
- Related content discovery
- Key insights generation

Architecture:
- prompts/: YAML prompt templates (easy to tune via files)
- providers/: AI provider abstraction (Gemini, OpenAI, etc.)
- services/: Business logic (summarizer, prompt_service, etc.)

All prompts are managed via YAML files for maintainability.
Use PromptService to load and format prompts.
"""

from .providers.gemini import GeminiProvider
from .services.summarizer import SummarizationService
from .services.prompt_service import (
    prompt_service,
    get_sector_research_prompt,
    get_kill_checklist_prompt,
    get_research_journal_prompt,
    get_research_template_prompt,
    get_competitor_analysis_prompt,
    get_document_processing_prompt
)

__all__ = [
    'GeminiProvider',
    'SummarizationService',
    'prompt_service',
    'get_sector_research_prompt',
    'get_kill_checklist_prompt',
    'get_research_journal_prompt',
    'get_research_template_prompt',
    'get_competitor_analysis_prompt',
    'get_document_processing_prompt'
]
