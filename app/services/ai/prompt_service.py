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
Prompt Management Service

Centralized management of LLM prompts for consistent, maintainable AI interactions.
Supports YAML-based prompt definitions with templating, versioning, and easy tuning.

Location: app/services/ai/prompt_service.py
Prompts:  app/services/ai/prompts/

Usage:
    from app.services.ai.prompt_service import prompt_service, get_kill_checklist_prompt
    
    # Get a formatted prompt
    prompt = prompt_service.get_prompt(
        'kill_checklist',
        'mistake_analysis',
        mistake_title="Bad investment",
        mistake_cost=25000
    )
    
    # Convenience functions
    prompt = get_kill_checklist_prompt('mistake_analysis', mistake_title="...", ...)
    prompt = get_research_journal_prompt('entry_analysis', entry_title="...", ...)
"""

import os
import yaml
import re
import logging
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from app.services.ai.config import AIModel, AIProvider as AIProviderEnum, get_ai_config
from app.models.user_ai_preferences import UserAIPreference

logger = logging.getLogger(__name__)


class PromptService:
    """
    Central service for managing and loading LLM prompts.
    
    Features:
    - YAML-based prompt definitions
    - Variable templating
    - Prompt caching
    - Metadata and versioning support
    """

    def __init__(self, prompts_dir: Optional[Path] = None):
        """
        Initialize prompt service.
        
        Args:
            prompts_dir: Custom prompts directory (defaults to ./prompts/)
        """
        if prompts_dir:
            self.prompts_dir = Path(prompts_dir)
        else:
            # Default: prompts directory relative to this file
            # This file: app/services/ai/prompt_service.py
            # Prompts:   app/services/ai/prompts/
            self.prompts_dir = Path(__file__).parent / "prompts"
        
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._load_all_prompts()

    def _load_all_prompts(self):
        """Load all prompt files at initialization for better performance."""
        if not self.prompts_dir.exists():
            logger.warning(f"Prompts directory not found: {self.prompts_dir}")
            logger.info("Creating prompts directory...")
            self.prompts_dir.mkdir(parents=True, exist_ok=True)
            return

        for category_dir in self.prompts_dir.iterdir():
            if category_dir.is_dir() and not category_dir.name.startswith('_'):
                category = category_dir.name
                self._cache[category] = {}

                for prompt_file in category_dir.glob("*.yaml"):
                    prompt_name = prompt_file.stem
                    try:
                        with open(prompt_file, 'r', encoding='utf-8') as f:
                            prompt_data = yaml.safe_load(f)
                            self._cache[category][prompt_name] = prompt_data
                            logger.debug(f"Loaded prompt: {category}/{prompt_name}")
                    except Exception as e:
                        logger.error(f"Failed to load prompt {category}/{prompt_name}: {e}")
        
        # Log summary
        total_prompts = sum(len(prompts) for prompts in self._cache.values())
        logger.info(f"Loaded {total_prompts} prompts from {len(self._cache)} categories")

    def get_prompt(self, category: str, name: str, **kwargs) -> str:
        """
        Get a prompt template and fill in variables.

        Args:
            category: Prompt category (e.g., 'kill_checklist', 'research_journal')
            name: Prompt name (e.g., 'mistake_analysis', 'entry_linking')
            **kwargs: Variables to substitute in the template

        Returns:
            Formatted prompt string ready for LLM

        Raises:
            ValueError: If category, name, or required variables are missing

        Example:
            prompt = prompt_service.get_prompt(
                'kill_checklist',
                'mistake_analysis',
                mistake_title="Bad investment",
                mistake_cost=25000
            )
        """
        if category not in self._cache:
            available = list(self._cache.keys())
            raise ValueError(f"Prompt category '{category}' not found. Available: {available}")

        if name not in self._cache[category]:
            available = list(self._cache[category].keys())
            raise ValueError(f"Prompt '{name}' not found in category '{category}'. Available: {available}")

        prompt_data = self._cache[category][name]

        # Build the complete prompt from sections
        prompt_sections = []

        # Add system context if present
        if 'system_context' in prompt_data:
            prompt_sections.append(prompt_data['system_context'])

        # Add main template
        if 'template' not in prompt_data:
            raise ValueError(f"Prompt '{category}/{name}' missing required 'template' field")

        template = prompt_data['template']

        # Apply variable substitution
        try:
            formatted_template = template.format(**kwargs)
            prompt_sections.append(formatted_template)
        except KeyError as e:
            missing_var = str(e).strip("'")
            required = self._extract_variables(template)
            raise ValueError(
                f"Missing required variable '{missing_var}' for prompt '{category}/{name}'. "
                f"Required: {required}, Provided: {list(kwargs.keys())}"
            )

        # Add examples if present
        if 'examples' in prompt_data and prompt_data['examples']:
            examples_section = "\n\nExamples:\n" + "\n".join([
                f"- {example}" for example in prompt_data['examples']
            ])
            prompt_sections.append(examples_section)

        # Add output format if present
        if 'output_format' in prompt_data:
            format_section = "\n\nExpected Output Format:\n" + prompt_data['output_format']
            prompt_sections.append(format_section)

        return "\n\n".join(prompt_sections)

    def get_prompt_info(self, category: str, name: str) -> Dict[str, Any]:
        """
        Get metadata about a prompt without formatting it.
        
        Args:
            category: Prompt category
            name: Prompt name
            
        Returns:
            Dict with prompt metadata
        """
        if category not in self._cache:
            raise ValueError(f"Prompt category '{category}' not found")

        if name not in self._cache[category]:
            raise ValueError(f"Prompt '{name}' not found in category '{category}'")

        prompt_data = self._cache[category][name]
        template = prompt_data.get('template', '')

        return {
            'name': prompt_data.get('name', name),
            'description': prompt_data.get('description', ''),
            'version': prompt_data.get('version', '1.0'),
            'category': category,
            'max_tokens': prompt_data.get('max_tokens', 2000),
            'temperature': prompt_data.get('temperature', 0.7),
            'preferred_provider': prompt_data.get('preferred_provider'),
            'model': prompt_data.get('model'),
            'required_variables': self._extract_variables(template),
            'has_system_context': 'system_context' in prompt_data,
            'has_output_format': 'output_format' in prompt_data,
            'has_examples': 'examples' in prompt_data and len(prompt_data.get('examples', [])) > 0,
            'last_modified': prompt_data.get('last_modified', 'unknown'),
        }

    def get_prompt_with_metadata(self, category: str, name: str, **kwargs) -> Dict[str, Any]:
        """
        Get both the formatted prompt and its metadata.

        Args:
            category: Prompt category
            name: Prompt name
            **kwargs: Variables for templating

        Returns:
            Dict with 'prompt', 'metadata', and optionally 'system_context' keys
        """
        prompt = self.get_prompt(category, name, **kwargs)
        metadata = self.get_prompt_info(category, name)

        # Also get system_context separately for providers that need it (e.g., Gemini)
        prompt_data = self._cache[category][name]
        system_context = prompt_data.get('system_context')

        return {
            'prompt': prompt,
            'metadata': metadata,
            'system_context': system_context,
            'rendered_length': len(prompt),
            'variables_used': kwargs
        }

    def list_categories(self) -> List[str]:
        """List all available prompt categories."""
        return list(self._cache.keys())

    def list_prompts(self, category: str) -> List[str]:
        """List all prompts in a category."""
        if category not in self._cache:
            raise ValueError(f"Category '{category}' not found")
        return list(self._cache[category].keys())

    def list_all_prompts(self) -> Dict[str, List[str]]:
        """List all prompts organized by category."""
        return {cat: list(prompts.keys()) for cat, prompts in self._cache.items()}

    def reload_prompts(self):
        """Reload all prompts from disk (useful for development)."""
        self._cache.clear()
        self._load_all_prompts()
        logger.info("Prompts reloaded")

    def test_prompt(self, category: str, name: str, **kwargs) -> Dict[str, Any]:
        """
        Test a prompt with sample variables without calling LLM.
        
        Returns rendered prompt and validation info.
        """
        try:
            prompt = self.get_prompt(category, name, **kwargs)
            metadata = self.get_prompt_info(category, name)
            
            return {
                'success': True,
                'prompt': prompt,
                'length': len(prompt),
                'estimated_tokens': len(prompt) // 4,
                'metadata': metadata
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'variables_provided': list(kwargs.keys())
            }

    def _extract_variables(self, template: str) -> List[str]:
        """Extract variable names from a template string."""
        # Find all {variable_name} patterns
        variables = re.findall(r'\{([^}:]+)', template)
        return list(set(variables))


# ============================================================
# Global Instance
# ============================================================

# Create singleton instance
prompt_service = PromptService()


# ============================================================
# Model / Provider Resolution
# ============================================================


def resolve_model_provider(
    metadata: Dict[str, Any],
    user_id: Optional[int] = None,
    prompt_category: Optional[str] = None,
) -> Tuple[Optional['AIModel'], Optional['AIProvider']]:
    """
    Resolve model and provider for a prompt using the priority chain:

    1. **User override** – ``UserAIPreference`` row for *(user_id, prompt_category)*.
       Checked only when both *user_id* and *prompt_category* are supplied.
    2. **YAML prompt config** – ``model`` / ``preferred_provider`` fields in the
       prompt metadata dict.

    Levels 3–4 (``AITaskType`` routing and environment-variable defaults) are
    handled downstream by ``AIService._get_provider()``.

    Returns ``(None, None)`` for any level that is missing or unrecognised so
    callers can fall through to task-based routing.

    Args:
        metadata: The ``metadata`` dict from ``get_prompt_with_metadata()``.
        user_id:  Current user's ID (optional).
        prompt_category: Prompt category string, e.g. ``'screening'`` (optional).

    Returns:
        (model_enum_or_None, provider_enum_or_None)
    """
    # ------------------------------------------------------------------
    # Priority 1: User override (UserAIPreference table)
    # ------------------------------------------------------------------
    if user_id and prompt_category:
        pref = UserAIPreference.get_preference(user_id, prompt_category)
        if pref and pref.model_override:
            try:
                model_enum = AIModel.from_string(pref.model_override)
                provider_enum = model_enum.provider
                logger.info(
                    "User %s override for '%s': %s",
                    user_id, prompt_category, pref.model_override,
                )
                return model_enum, provider_enum
            except (ValueError, KeyError):
                logger.warning(
                    "Invalid user model override '%s' for user %s, "
                    "category '%s' – falling through to YAML config",
                    pref.model_override, user_id, prompt_category,
                )

    # ------------------------------------------------------------------
    # Priority 2: YAML prompt metadata
    # ------------------------------------------------------------------
    model_enum = None
    provider_enum = None

    model_str = metadata.get('model')
    if model_str:
        try:
            model_enum = AIModel.from_string(model_str)
        except (ValueError, KeyError):
            logger.warning(f"Unknown model in prompt metadata: {model_str}")

    provider_str = metadata.get('preferred_provider')
    if provider_str:
        try:
            provider_enum = AIProviderEnum(provider_str)
        except (ValueError, KeyError):
            logger.warning(f"Unknown provider in prompt metadata: {provider_str}")

    return model_enum, provider_enum


# Display-friendly model names (model_id → label)
_MODEL_DISPLAY_NAMES = {
    'gemini-3-flash-preview': 'Gemini 3 Flash',
    'gemini-3-pro-preview': 'Gemini 3 Pro',
    'gemini-2.5-flash': 'Gemini 2.5 Flash',
    'gemini-2.5-pro': 'Gemini 2.5 Pro',
    'gemini-2.5-flash-lite': 'Gemini 2.5 Flash Lite',
    'gemini-flash-latest': 'Gemini Flash (Latest)',
    'gemini-pro-latest': 'Gemini Pro (Latest)',
    'claude-sonnet-4-20250514': 'Claude Sonnet 4',
    'claude-opus-4-20250514': 'Claude Opus 4',
    'claude-3-5-haiku-20241022': 'Claude 3.5 Haiku',
    'deepseek-chat': 'DeepSeek V3',
    'deepseek-reasoner': 'DeepSeek R1',
}


def get_effective_model_display(
    prompt_category: str,
    user_id: Optional[int] = None,
) -> str:
    """
    Return a display-friendly name for the model that will be used for
    a given prompt category and user, following the priority chain.

    Useful for showing "AI Model: Claude Sonnet 4" in templates without
    hardcoding model names.

    Priority:
        1. User override (``UserAIPreference``)
        2. YAML prompt config (first prompt in the category)
        3. Environment default (``AIConfig.default_model``)

    Args:
        prompt_category: Prompt category, e.g. ``'portfolio'``, ``'screening'``.
        user_id: Current user's ID (optional).

    Returns:
        Human-readable model name string.
    """
    # Priority 1: user override
    if user_id:
        pref = UserAIPreference.get_preference(user_id, prompt_category)
        if pref and pref.model_override:
            try:
                model = AIModel.from_string(pref.model_override)
                return _MODEL_DISPLAY_NAMES.get(model.model_id, model.model_id)
            except (ValueError, KeyError):
                pass

    # Priority 2: YAML prompt metadata (use first prompt in category)
    if prompt_category in prompt_service._cache:
        prompts = list(prompt_service._cache[prompt_category].keys())
        if prompts:
            try:
                info = prompt_service.get_prompt_info(prompt_category, prompts[0])
                model_str = info.get('model')
                if model_str:
                    model = AIModel.from_string(model_str)
                    return _MODEL_DISPLAY_NAMES.get(model.model_id, model.model_id)
            except (ValueError, KeyError):
                pass

    # Priority 3: environment default
    config = get_ai_config()
    return _MODEL_DISPLAY_NAMES.get(
        config.default_model.model_id, config.default_model.model_id,
    )


# ============================================================
# Convenience Functions
# ============================================================

def get_kill_checklist_prompt(name: str, **kwargs) -> str:
    """Convenience function for kill checklist prompts."""
    return prompt_service.get_prompt('kill_checklist', name, **kwargs)


def get_research_journal_prompt(name: str, **kwargs) -> str:
    """Convenience function for research journal prompts."""
    return prompt_service.get_prompt('research_journal', name, **kwargs)


def get_research_template_prompt(name: str, **kwargs) -> str:
    """Convenience function for research template prompts."""
    return prompt_service.get_prompt('research_template', name, **kwargs)


def get_sector_research_prompt(name: str, **kwargs) -> str:
    """Convenience function for sector research prompts."""
    return prompt_service.get_prompt('sector_research', name, **kwargs)


def get_document_processing_prompt(name: str, **kwargs) -> str:
    """Convenience function for document processing prompts."""
    return prompt_service.get_prompt('document_processing', name, **kwargs)


def get_competitor_analysis_prompt(name: str, **kwargs) -> str:
    """Convenience function for competitor analysis prompts."""
    return prompt_service.get_prompt('competitor_analysis', name, **kwargs)


def get_intelligence_prompt(name: str, **kwargs) -> str:
    """Convenience function for intelligence prompts."""
    return prompt_service.get_prompt('intelligence', name, **kwargs)


def get_checkpoint_prompt(name: str, **kwargs) -> str:
    """Convenience function for checkpoint prompts."""
    return prompt_service.get_prompt('checkpoint', name, **kwargs)


def list_all_prompts() -> Dict[str, List[str]]:
    """List all available prompts."""
    return prompt_service.list_all_prompts()


def test_prompt(category: str, name: str, **kwargs) -> Dict[str, Any]:
    """Test a prompt with sample variables."""
    return prompt_service.test_prompt(category, name, **kwargs)
