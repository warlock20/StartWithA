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
