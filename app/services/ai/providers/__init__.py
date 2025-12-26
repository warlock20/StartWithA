"""
AI Providers Package

This package contains implementations for different AI providers.

Available Providers:
    - GeminiProvider: Google Gemini API
    - ClaudeProvider: Anthropic Claude API

Usage:
    from app.services.ai.providers import GeminiProvider, ClaudeProvider
    
    # Create provider with default model
    gemini = GeminiProvider()
    claude = ClaudeProvider()
    
    # Create with specific model
    from app.services.ai.config import AIModel
    gemini = GeminiProvider(model=AIModel.GEMINI_PRO_25)
"""

from .base import AIProvider
from .gemini import GeminiProvider
from .claude import ClaudeProvider

__all__ = [
    'AIProvider',
    'GeminiProvider', 
    'ClaudeProvider',
]
