"""
AI Intelligence Service - Provider-Agnostic with Smart Routing

This service provides investment intelligence features using configurable AI routing:
- Loads routing rules from app/config/ai_routing.yaml
- Loads prompt templates from app/ai/prompts/intelligence/
- Routes to optimal provider (Claude/Gemini) based on task and config
- Handles automatic fallback if primary provider unavailable
"""

import os
import logging
import yaml
import json
from typing import Dict, Any, Optional
from pathlib import Path
import anthropic

from .llm_service import UnifiedLLMService, LLMProvider

logger = logging.getLogger(__name__)


class IntelligenceService:
    """
    Smart AI service with configurable routing and prompt management

    Features:
    - Provider-agnostic: works with Claude, Gemini, or any configured provider
    - Config-driven routing: change providers via YAML without code changes
    - Automatic fallback: if primary provider unavailable, uses fallback
    - Prompt templates: prompts stored in YAML for easy modification
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize intelligence service

        Args:
            config_path: Optional path to ai_routing.yaml, defaults to app/config/ai_routing.yaml
        """
        # Load routing configuration
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'config', 'ai_routing.yaml'
            )

        self.config = self._load_config(config_path)
        self.prompts_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'ai', 'prompts', 'intelligence'
        )

        # Initialize provider clients
        self._init_providers()

    def _load_config(self, config_path: str) -> Dict:
        """Load routing configuration from YAML"""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load AI routing config: {e}")
            # Return default config as fallback
            return self._get_default_config()

    def _get_default_config(self) -> Dict:
        """Default configuration if YAML not found"""
        return {
            'routing_rules': {
                'thesis_analysis': {'primary': 'gemini', 'fallback': 'none'},
                'warning_generation': {'primary': 'gemini', 'fallback': 'none'},
                'pattern_explanation': {'primary': 'gemini', 'fallback': 'none'},
            },
            'providers': {
                'claude': {'api_key_env': 'ANTHROPIC_API_KEY'},
                'gemini': {'api_key_env': 'GEMINI_API_KEY'}
            },
            'cost_optimization': {'enable_fallback': True}
        }

    def _init_providers(self):
        """Initialize available AI providers"""
        self.providers = {}

        # Initialize Claude if API key available
        claude_config = self.config['providers'].get('claude', {})
        claude_api_key = os.getenv(claude_config.get('api_key_env', 'ANTHROPIC_API_KEY'))
        if claude_api_key:
            try:
                self.providers['claude'] = anthropic.Anthropic(api_key=claude_api_key)
                logger.info("Claude provider initialized")
            except Exception as e:
                logger.warning(f"Claude initialization failed: {e}")

        # Initialize Gemini if available
        gemini_config = self.config['providers'].get('gemini', {})
        gemini_api_key = os.getenv(gemini_config.get('api_key_env', 'GEMINI_API_KEY'))
        if gemini_api_key:
            try:
                self.providers['gemini'] = UnifiedLLMService(LLMProvider.GEMINI)
                logger.info("Gemini provider initialized")
            except Exception as e:
                logger.warning(f"Gemini initialization failed: {e}")

    def _load_prompt_template(self, template_name: str) -> Dict:
        """Load prompt template from YAML"""
        template_path = os.path.join(self.prompts_dir, f"{template_name}.yaml")
        try:
            with open(template_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load prompt template {template_name}: {e}")
            raise

    def _format_prompt(self, template: Dict, variables: Dict[str, Any]) -> str:
        """
        Format prompt template with variables

        Args:
            template: Loaded YAML template
            variables: Dictionary of variables to substitute

        Returns:
            Formatted prompt string
        """
        prompt_text = template['template']

        # Replace all {variable} placeholders
        for key, value in variables.items():
            placeholder = f"{{{key}}}"
            if placeholder in prompt_text:
                # Handle None values
                if value is None:
                    value = "Not provided"
                prompt_text = prompt_text.replace(placeholder, str(value))

        return prompt_text

    def _get_provider_for_task(self, task_name: str) -> tuple[Optional[Any], str]:
        """
        Get the appropriate provider for a task based on routing config

        Returns:
            (provider_client, provider_name) tuple
        """
        routing = self.config['routing_rules'].get(task_name, {})
        primary = routing.get('primary', 'gemini')
        fallback = routing.get('fallback', 'none')
        enable_fallback = self.config['cost_optimization'].get('enable_fallback', True)

        # Try primary provider
        if primary in self.providers:
            return self.providers[primary], primary

        # Try fallback if enabled
        if enable_fallback and fallback != 'none' and fallback in self.providers:
            logger.warning(f"Primary provider '{primary}' unavailable for {task_name}, using fallback '{fallback}'")
            return self.providers[fallback], fallback

        raise RuntimeError(f"No available provider for task '{task_name}'. Primary='{primary}', Fallback='{fallback}'")

    def _call_claude(self, prompt: str, template: Dict) -> Dict[str, Any]:
        """Call Claude API"""
        client = self.providers['claude']
        model = self.config['providers']['claude'].get('default_model', 'claude-sonnet-4-20250514')
        max_tokens = template.get('max_tokens', 2000)

        try:
            message = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text

            # Try to parse as JSON if output_format suggests JSON
            if template.get('output_format') and '{' in template['output_format']:
                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    logger.warning("Claude response not valid JSON, returning as text")
                    return {'response': response_text}

            return {'response': response_text}

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise

    def _call_gemini(self, prompt: str, template: Dict) -> Dict[str, Any]:
        """Call Gemini API"""
        service = self.providers['gemini']

        try:
            # Check if we expect JSON output
            if template.get('output_format') and '{' in template['output_format']:
                response = service.generate_json(prompt)
                return response
            else:
                response_text = service.generate_content(prompt)
                return {'response': response_text}

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise

    def analyze_thesis(
        self,
        company_name: str,
        thesis_text: str,
        research_data: Dict[str, Any],
        historical_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Analyze investment thesis quality

        Args:
            company_name: Company being analyzed
            thesis_text: Investment thesis to analyze
            research_data: Dict with questions_answered, documents_analyzed, etc.
            historical_context: Optional user's past patterns

        Returns:
            {
                'quality_assessment': str,
                'strengths': List[str],
                'weaknesses': List[str],
                'blind_spots': List[str],
                'suggested_questions': List[str],
                'confidence_adjustment': int,
                'risk_flags': List[str]
            }
        """
        # Load prompt template
        template = self._load_prompt_template('thesis_analysis')

        # Build historical context section
        history_text = ""
        if historical_context:
            history_text = f"""
HISTORICAL CONTEXT FROM USER'S PAST INVESTMENTS:
- Similar companies researched: {historical_context.get('similar_companies', 'None')}
- Past mistakes in this sector: {historical_context.get('sector_mistakes', 'None')}
- User's typical blind spots: {historical_context.get('blind_spots', 'None')}
"""

        # Format prompt
        variables = {
            'company_name': company_name,
            'thesis_text': thesis_text,
            'questions_answered': research_data.get('questions_answered', 0),
            'questions_total': research_data.get('questions_total', 0),
            'documents_analyzed': research_data.get('documents_analyzed', 0),
            'research_duration_hours': research_data.get('research_duration_minutes', 0) / 60,
            'key_findings': research_data.get('key_findings', 'Not provided'),
            'identified_risks': research_data.get('identified_risks', 'Not provided'),
            'historical_context': history_text
        }

        prompt = self._format_prompt(template, variables)

        # Get provider and call
        provider, provider_name = self._get_provider_for_task('thesis_analysis')

        if provider_name == 'claude':
            return self._call_claude(prompt, template)
        else:  # gemini
            return self._call_gemini(prompt, template)

    def generate_warning(
        self,
        warning_context: Dict[str, Any],
        user_patterns: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate contextual warning based on detected patterns

        Args:
            warning_context: Dict with situation_description, company_name, action, pattern_description
            user_patterns: Dict with similar_situations, outcomes, common_mistakes

        Returns:
            {
                'title': str,
                'warning_text': str,
                'severity': str,
                'evidence': List[str],
                'suggested_action': str,
                'related_past_mistakes': List[str]
            }
        """
        template = self._load_prompt_template('warning_generation')

        variables = {
            'situation_description': warning_context.get('situation_description', ''),
            'company_name': warning_context.get('company_name', 'Unknown'),
            'action': warning_context.get('action', 'Unknown'),
            'pattern_description': warning_context.get('pattern_description', ''),
            'similar_situations': user_patterns.get('similar_situations', 'None recorded'),
            'outcomes': user_patterns.get('outcomes', 'Unknown'),
            'common_mistakes': user_patterns.get('common_mistakes', 'None recorded'),
            'success_patterns': user_patterns.get('success_patterns', 'None recorded')
        }

        prompt = self._format_prompt(template, variables)
        provider, provider_name = self._get_provider_for_task('warning_generation')

        if provider_name == 'claude':
            return self._call_claude(prompt, template)
        else:
            return self._call_gemini(prompt, template)

    def explain_pattern(
        self,
        pattern_type: str,
        pattern_data: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> str:
        """
        Explain behavioral pattern in plain language

        Args:
            pattern_type: Type of pattern (e.g., "disposition_effect")
            pattern_data: Data about the detected pattern
            user_context: Dict with experience_level, portfolio_size, investment_style

        Returns:
            Human-readable explanation (2-3 paragraphs)
        """
        template = self._load_prompt_template('pattern_explanation')

        variables = {
            'pattern_type': pattern_type,
            'pattern_data_json': json.dumps(pattern_data, indent=2),
            'experience_level': user_context.get('experience_level', 'Unknown'),
            'portfolio_size': user_context.get('portfolio_size', 'Unknown'),
            'investment_style': user_context.get('investment_style', 'Unknown'),
            'holding_period': user_context.get('holding_period', 'Unknown')
        }

        prompt = self._format_prompt(template, variables)
        provider, provider_name = self._get_provider_for_task('pattern_explanation')

        if provider_name == 'claude':
            result = self._call_claude(prompt, template)
            return result.get('response', '')
        else:
            result = self._call_gemini(prompt, template)
            return result.get('response', '')
