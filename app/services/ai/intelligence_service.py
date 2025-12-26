"""
AI Intelligence Service - Fully Config-Driven

Architecture:
1. Prompts define their preferred provider, model, and parameters
2. ai_routing.yaml can override any prompt defaults
3. IntelligenceService merges configs and calls providers generically
4. NO hardcoded provider logic - fully flexible
"""

import os
import logging
import yaml
import json
from typing import Dict, Any, Optional

from app.services.ai import ClaudeProvider, GeminiProvider

logger = logging.getLogger(__name__)


class IntelligenceService:
    """
    Config-driven AI service - NO hardcoding!

    Flow:
      1. Load prompt template → get defaults (provider, model, params)
      2. Check ai_routing.yaml → get overrides (optional)
      3. Merge configs → final config
      4. Get provider from registry
      5. Call provider.generate_text() → generic!
      6. Parse response
    """

    def __init__(self, config_path: Optional[str] = None):
        """Initialize intelligence service"""
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

        # Initialize provider registry
        self._init_provider_registry()

    def _load_config(self, config_path: str) -> Dict:
        """Load routing configuration from YAML"""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load AI routing config: {e}")
            return {'task_overrides': {}, 'providers': {}, 'settings': {}}

    def _init_provider_registry(self):
        """Initialize provider registry with all available providers"""
        self.provider_registry = {}

        # Initialize each provider if API key is available
        for provider_name, provider_config in self.config.get('providers', {}).items():
            api_key_env = provider_config.get('api_key_env')
            api_key = os.getenv(api_key_env)

            if not api_key:
                logger.warning(f"{provider_name} API key not found ({api_key_env})")
                continue

            try:
                if provider_name == 'claude':
                    self.provider_registry['claude'] = ClaudeProvider(api_key=api_key)
                    logger.info(f"✓ Claude provider initialized")
                elif provider_name == 'gemini':
                    self.provider_registry['gemini'] = GeminiProvider(api_key=api_key)
                    logger.info(f"✓ Gemini provider initialized")
                else:
                    logger.warning(f"Unknown provider: {provider_name}")

            except Exception as e:
                logger.error(f"Failed to initialize {provider_name}: {e}")

    def _load_prompt_template(self, template_name: str) -> Dict:
        """Load prompt template from YAML"""
        template_path = os.path.join(self.prompts_dir, f"{template_name}.yaml")
        try:
            with open(template_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load prompt template {template_name}: {e}")
            raise

    def _get_task_config(self, template_name: str, template: Dict) -> Dict:
        """
        Merge prompt template defaults with routing config overrides

        Priority: ai_routing.yaml task_overrides > prompt template defaults
        """
        # Start with prompt template defaults
        config = {
            'provider': template.get('preferred_provider', 'gemini'),
            'model': template.get('model'),
            'max_tokens': template.get('max_tokens', 2000),
            'temperature': template.get('temperature', 0.7)
        }

        # Apply overrides from ai_routing.yaml if they exist
        task_overrides = self.config.get('task_overrides', {}).get(template_name, {})
        if task_overrides:
            logger.info(f"Applying config overrides for {template_name}: {task_overrides}")
            config.update(task_overrides)

        return config

    def _format_prompt(self, template: Dict, variables: Dict[str, Any]) -> str:
        """Format prompt template with variables"""
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

    def _get_provider(self, provider_name: str) -> Any:
        """
        Get provider from registry with automatic fallback

        Args:
            provider_name: Name of preferred provider

        Returns:
            Provider instance

        Raises:
            RuntimeError: If no providers available
        """
        # Try preferred provider first
        if provider_name in self.provider_registry:
            provider = self.provider_registry[provider_name]
            if provider.is_available():
                return provider
            else:
                logger.warning(f"{provider_name} not available, trying fallback")

        # Try fallback if enabled
        if self.config.get('settings', {}).get('enable_fallback', True):
            fallback = self.config.get('settings', {}).get('default_fallback', 'gemini')

            if fallback != provider_name and fallback in self.provider_registry:
                logger.info(f"Using fallback provider: {fallback}")
                provider = self.provider_registry[fallback]
                if provider.is_available():
                    return provider

        # No providers available
        available = [name for name, p in self.provider_registry.items() if p.is_available()]
        raise RuntimeError(
            f"No available AI provider. Requested: {provider_name}, "
            f"Available: {available or 'none'}"
        )

    def _call_provider(self, provider: Any, prompt: str, config: Dict) -> str:
        """
        Call AI provider generically - NO hardcoded provider logic!

        Args:
            provider: The provider instance (ClaudeProvider or GeminiProvider)
            prompt: Formatted prompt text
            config: Config dict with model, max_tokens, temperature

        Returns:
            Generated text response
        """
        return provider.generate_text(
            prompt=prompt,
            max_tokens=config.get('max_tokens'),
            temperature=config.get('temperature')
        )

    def _parse_response(self, response_text: str, template: Dict) -> Any:
        """
        Parse AI response based on template's output_format

        If output_format contains JSON structure, try to parse as JSON
        Otherwise return raw text
        """
        output_format = template.get('output_format', '')

        # Check if JSON output is expected
        if '{' in output_format and '}' in output_format:
            try:
                # Try to parse as JSON
                return json.loads(response_text)
            except json.JSONDecodeError:
                logger.warning("Expected JSON output but parsing failed, returning raw text")
                # Return in dict format for consistency
                return {'response': response_text}

        # Return raw text
        return {'response': response_text}

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
            Analysis results (format defined in prompt template)
        """
        template_name = 'thesis_analysis'

        # 1. Load prompt template
        template = self._load_prompt_template(template_name)

        # 2. Get merged config (template defaults + routing overrides)
        config = self._get_task_config(template_name, template)

        # 3. Build historical context section
        history_text = ""
        if historical_context:
            history_text = f"""
HISTORICAL CONTEXT FROM USER'S PAST INVESTMENTS:
- Similar companies researched: {historical_context.get('similar_companies', 'None')}
- Past mistakes in this sector: {historical_context.get('sector_mistakes', 'None')}
- User's typical blind spots: {historical_context.get('blind_spots', 'None')}
"""

        # 4. Format prompt with variables
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

        # 5. Get provider (generic!)
        provider = self._get_provider(config['provider'])

        # 6. Call provider (generic!)
        logger.info(f"Calling {config['provider']} for {template_name}")
        response = self._call_provider(provider, prompt, config)

        # 7. Parse response
        return self._parse_response(response, template)

    def generate_warning(
        self,
        warning_context: Dict[str, Any],
        user_patterns: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate contextual warning based on detected patterns"""
        template_name = 'warning_generation'

        template = self._load_prompt_template(template_name)
        config = self._get_task_config(template_name, template)

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
        provider = self._get_provider(config['provider'])

        logger.info(f"Calling {config['provider']} for {template_name}")
        response = self._call_provider(provider, prompt, config)

        return self._parse_response(response, template)

    def explain_pattern(
        self,
        pattern_type: str,
        pattern_data: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> str:
        """Explain behavioral pattern in plain language"""
        template_name = 'pattern_explanation'

        template = self._load_prompt_template(template_name)
        config = self._get_task_config(template_name, template)

        variables = {
            'pattern_type': pattern_type,
            'pattern_data_json': json.dumps(pattern_data, indent=2),
            'experience_level': user_context.get('experience_level', 'Unknown'),
            'portfolio_size': user_context.get('portfolio_size', 'Unknown'),
            'investment_style': user_context.get('investment_style', 'Unknown'),
            'holding_period': user_context.get('holding_period', 'Unknown')
        }

        prompt = self._format_prompt(template, variables)
        provider = self._get_provider(config['provider'])

        logger.info(f"Calling {config['provider']} for {template_name}")
        response = self._call_provider(provider, prompt, config)

        result = self._parse_response(response, template)
        return result.get('response', response) if isinstance(result, dict) else result
