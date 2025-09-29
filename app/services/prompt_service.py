"""
Prompt Management Service

Centralized management of LLM prompts for consistent, maintainable AI interactions.
Supports YAML-based prompt definitions with templating, versioning, and easy tuning.
"""

import os
import yaml
from typing import Dict, Any, Optional, List
from pathlib import Path
import re
from datetime import datetime


class PromptService:
    """Central service for managing and loading LLM prompts"""

    def __init__(self):
        self.prompts_dir = Path(__file__).parent.parent / "prompts"
        self._cache = {}  # Simple in-memory cache
        self._load_all_prompts()

    def _load_all_prompts(self):
        """Load all prompt files at initialization for better performance"""
        if not self.prompts_dir.exists():
            raise FileNotFoundError(f"Prompts directory not found: {self.prompts_dir}")

        for category_dir in self.prompts_dir.iterdir():
            if category_dir.is_dir():
                category = category_dir.name
                self._cache[category] = {}

                for prompt_file in category_dir.glob("*.yaml"):
                    prompt_name = prompt_file.stem
                    try:
                        with open(prompt_file, 'r', encoding='utf-8') as f:
                            prompt_data = yaml.safe_load(f)
                            self._cache[category][prompt_name] = prompt_data
                    except Exception as e:
                        print(f"Warning: Failed to load prompt {category}/{prompt_name}: {e}")

    def get_prompt(self, category: str, name: str, **kwargs) -> str:
        """
        Get a prompt template and fill in variables.

        Args:
            category: Prompt category (e.g., 'kill_checklist', 'research_journal')
            name: Prompt name (e.g., 'mistake_analysis', 'entry_linking')
            **kwargs: Variables to substitute in the template

        Returns:
            Formatted prompt string ready for LLM

        Example:
            prompt = prompt_service.get_prompt(
                'kill_checklist',
                'mistake_analysis',
                mistake_title="Bad investment",
                mistake_cost=25000
            )
        """
        if category not in self._cache:
            raise ValueError(f"Prompt category '{category}' not found. Available: {list(self._cache.keys())}")

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
            raise ValueError(f"Missing required variable '{missing_var}' for prompt '{category}/{name}'")

        # Add examples if present
        if 'examples' in prompt_data and prompt_data['examples']:
            examples_section = "\n\nExamples:\n" + "\n".join([
                f"Example {i+1}: {example}"
                for i, example in enumerate(prompt_data['examples'])
            ])
            prompt_sections.append(examples_section)

        # Add output format if present
        if 'output_format' in prompt_data:
            format_section = "\n\nOutput Format:\n" + prompt_data['output_format']
            prompt_sections.append(format_section)

        return "\n\n".join(prompt_sections)

    def get_prompt_info(self, category: str, name: str) -> Dict[str, Any]:
        """Get metadata about a prompt without formatting it"""
        if category not in self._cache:
            raise ValueError(f"Prompt category '{category}' not found")

        if name not in self._cache[category]:
            raise ValueError(f"Prompt '{name}' not found in category '{category}'")

        prompt_data = self._cache[category][name].copy()

        # Extract metadata
        metadata = {
            'name': name,
            'category': category,
            'description': prompt_data.get('description', 'No description'),
            'version': prompt_data.get('version', '1.0'),
            'required_variables': self._extract_variables(prompt_data.get('template', '')),
            'max_tokens': prompt_data.get('max_tokens', 1000),
            'temperature': prompt_data.get('temperature', 0.7),
            'last_modified': prompt_data.get('last_modified', 'Unknown')
        }

        return metadata

    def list_prompts(self, category: Optional[str] = None) -> Dict[str, List[str]]:
        """List all available prompts, optionally filtered by category"""
        if category:
            if category not in self._cache:
                return {category: []}
            return {category: list(self._cache[category].keys())}

        return {cat: list(prompts.keys()) for cat, prompts in self._cache.items()}

    def validate_prompt(self, category: str, name: str, **kwargs) -> Dict[str, Any]:
        """Validate that a prompt can be rendered with given variables"""
        try:
            prompt = self.get_prompt(category, name, **kwargs)
            return {
                'valid': True,
                'prompt_length': len(prompt),
                'word_count': len(prompt.split()),
                'variables_used': list(kwargs.keys())
            }
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'variables_provided': list(kwargs.keys())
            }

    def reload_prompts(self):
        """Reload all prompts from disk (useful for development)"""
        self._cache.clear()
        self._load_all_prompts()

    def _extract_variables(self, template: str) -> List[str]:
        """Extract variable names from a template string"""
        # Find all {variable_name} patterns
        variables = re.findall(r'\{([^}]+)\}', template)
        # Remove format specifiers (e.g., {cost:.2f} -> cost)
        cleaned_variables = [var.split(':')[0] for var in variables]
        return list(set(cleaned_variables))

    def get_prompt_with_metadata(self, category: str, name: str, **kwargs) -> Dict[str, Any]:
        """Get both the formatted prompt and its metadata"""
        prompt = self.get_prompt(category, name, **kwargs)
        metadata = self.get_prompt_info(category, name)

        return {
            'prompt': prompt,
            'metadata': metadata,
            'rendered_length': len(prompt),
            'variables_used': kwargs
        }


# Global instance for easy importing
prompt_service = PromptService()


# Convenience functions for common use cases
def get_kill_checklist_prompt(name: str, **kwargs) -> str:
    """Convenience function for kill checklist prompts"""
    return prompt_service.get_prompt('kill_checklist', name, **kwargs)


def get_research_journal_prompt(name: str, **kwargs) -> str:
    """Convenience function for research journal prompts"""
    return prompt_service.get_prompt('research_journal', name, **kwargs)


def get_research_template_prompt(name: str, **kwargs) -> str:
    """Convenience function for research template prompts"""
    return prompt_service.get_prompt('research_template', name, **kwargs)


def get_competitor_analysis_prompt(name: str, **kwargs) -> str:
    """Convenience function for competitor analysis prompts"""
    return prompt_service.get_prompt('competitor_analysis', name, **kwargs)


# Development helper functions
def list_all_prompts():
    """Debug function to list all available prompts"""
    prompts = prompt_service.list_prompts()
    print("📋 Available Prompts:")
    for category, names in prompts.items():
        print(f"  {category}:")
        for name in names:
            metadata = prompt_service.get_prompt_info(category, name)
            print(f"    - {name}: {metadata['description']}")
    return prompts


def test_prompt(category: str, name: str, **kwargs):
    """Debug function to test a prompt with sample data"""
    try:
        result = prompt_service.get_prompt_with_metadata(category, name, **kwargs)
        print(f"✅ Prompt {category}/{name} rendered successfully")
        print(f"   Length: {result['rendered_length']} chars")
        print(f"   Variables: {result['variables_used']}")
        print(f"   Preview: {result['prompt'][:200]}...")
        return True
    except Exception as e:
        print(f"❌ Prompt {category}/{name} failed: {e}")
        return False