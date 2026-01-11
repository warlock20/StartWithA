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
from app.services.ai.config import AIModel

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
                os.path.dirname(__file__),
                'prompts', 'ai_routing.yaml'
            )

        self.config = self._load_config(config_path)

        # Base prompts directory - supports subdirectories for different categories
        self.prompts_base_dir = os.path.join(
            os.path.dirname(__file__),
            'prompts'
        )

        # Initialize provider registry
        self._init_provider_registry()

    def _load_config(self, config_path: str) -> Dict:
        """Load routing configuration from YAML"""
        default_config = {'task_overrides': {}, 'providers': {}, 'settings': {}}

        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            # Handle empty/None YAML files
            if config is None:
                logger.warning(f"AI routing config is empty, using defaults")
                return default_config

            return config
        except Exception as e:
            logger.error(f"Failed to load AI routing config: {e}")
            return default_config

    def _init_provider_registry(self):
        """
        Initialize provider registry.

        Note: Providers are now cached by model (e.g., 'gemini:gemini-2.5-flash')
        and created on-demand in _get_provider() to respect per-task model configs.

        This method checks API key availability but doesn't pre-create providers.
        """
        self.provider_registry = {}

        # Store available providers (those with API keys)
        self.available_providers = set()

        # Safety check
        if self.config is None:
            logger.error("Cannot initialize providers: config is None")
            return

        # Check which providers have API keys available
        for provider_name, provider_config in self.config.get('providers', {}).items():
            api_key_env = provider_config.get('api_key_env')
            api_key = os.getenv(api_key_env)

            if api_key:
                self.available_providers.add(provider_name)
                logger.info(f"✓ {provider_name} API key found, provider available")
            else:
                logger.warning(f"✗ {provider_name} API key not found ({api_key_env})")

    def _load_prompt_template(self, template_name: str) -> Dict:
        """
        Load prompt template from YAML.

        Searches in multiple subdirectories:
        - prompts/portfolio/ (portfolio-specific prompts)
        - prompts/intelligence/ (general intelligence prompts)

        Args:
            template_name: Name of template (with or without .yaml extension)

        Returns:
            Loaded template dict
        """
        # Remove .yaml extension if provided
        if template_name.endswith('.yaml'):
            template_name = template_name[:-5]

        # Search in subdirectories
        search_dirs = ['portfolio', 'intelligence']

        for subdir in search_dirs:
            template_path = os.path.join(self.prompts_base_dir, subdir, f"{template_name}.yaml")
            if os.path.exists(template_path):
                try:
                    with open(template_path, 'r') as f:
                        template = yaml.safe_load(f)
                        logger.info(f"Loaded template '{template_name}' from {subdir}/")
                        return template
                except Exception as e:
                    logger.error(f"Failed to load template {template_name} from {template_path}: {e}")
                    continue

        # Template not found in any directory
        raise FileNotFoundError(
            f"Prompt template '{template_name}' not found in: {', '.join(search_dirs)}"
        )

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
        # Safety check: handle None config or None task_overrides
        if self.config is None:
            logger.warning("AI routing config is None, using template defaults only")
            return config

        # Handle case where task_overrides exists but is None (empty YAML section)
        task_overrides_dict = self.config.get('task_overrides') or {}
        task_overrides = task_overrides_dict.get(template_name, {})
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

    def _get_provider(self, provider_name: str, model_name: Optional[str] = None) -> Any:
        """
        Get provider from registry with model-specific caching.

        Providers are cached by "provider:model" key (e.g., "gemini:gemini-2.5-flash").
        This allows different tasks to use different models from the same provider.

        Args:
            provider_name: Name of provider (e.g., 'gemini', 'claude')
            model_name: Model to use (e.g., 'gemini-2.5-flash'). If None, uses default.

        Returns:
            Provider instance configured for the specified model

        Raises:
            RuntimeError: If no providers available
        """
        # Import here to avoid circular dependency
        from app.services.ai import AIModel

        # Check if provider API key is available
        if provider_name not in self.available_providers:
            # Try fallback
            if self.config.get('settings', {}).get('enable_fallback', True):
                fallback = self.config.get('settings', {}).get('default_fallback', 'gemini')
                if fallback != provider_name and fallback in self.available_providers:
                    logger.info(f"Provider {provider_name} not available, using fallback: {fallback}")
                    provider_name = fallback
                else:
                    raise RuntimeError(f"Provider {provider_name} not available and no fallback found")
            else:
                raise RuntimeError(f"Provider {provider_name} not available")

        # Convert model string to AIModel enum
        model_enum = AIModel.from_string(model_name) if model_name else None

        # Build cache key: "provider:model_id"
        cache_key = f"{provider_name}:{model_enum.model_id if model_enum else 'default'}"

        # Check if we already have this provider+model cached
        if cache_key in self.provider_registry:
            logger.debug(f"Using cached provider: {cache_key}")
            return self.provider_registry[cache_key]

        # Create new provider instance with specified model
        logger.info(f"Creating new provider instance: {cache_key}")

        try:
            if provider_name == 'gemini':
                
                provider = GeminiProvider(model=model_enum)
            elif provider_name == 'claude':
                provider = ClaudeProvider(model=model_enum)
            else:
                raise RuntimeError(f"Unknown provider: {provider_name}")

            # Cache it for future use
            self.provider_registry[cache_key] = provider
            logger.info(f"✓ Provider created and cached: {cache_key}")

            return provider

        except Exception as e:
            logger.error(f"Failed to create provider {cache_key}: {e}")
            raise RuntimeError(f"Failed to create provider {provider_name}: {e}")

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
                # Strip markdown code fences if present (Gemini often wraps JSON in ```json ... ```)
                cleaned_text = response_text.strip()

                logger.info(f"Original response starts with: {cleaned_text[:50]}")
                logger.info(f"Original response ends with: {cleaned_text[-50:]}")

                if cleaned_text.startswith('```'):
                    # Find the first newline after opening fence
                    first_newline = cleaned_text.find('\n')
                    # Find the closing fence
                    last_fence = cleaned_text.rfind('```')
                    logger.info(f"Found fence markers: first_newline={first_newline}, last_fence={last_fence}")
                    if first_newline > 0 and last_fence > first_newline:
                        cleaned_text = cleaned_text[first_newline + 1:last_fence].strip()
                        logger.info(f"Stripped fences, new length: {len(cleaned_text)}")

                # Try to parse as JSON
                logger.info(f"Attempting to parse JSON (length: {len(cleaned_text)} chars)")
                logger.info(f"First 200 chars: {cleaned_text[:200]}")
                logger.info(f"Last 200 chars: {cleaned_text[-200:]}")
                parsed = json.loads(cleaned_text)
                logger.info(f"✓ JSON parsed successfully, keys: {list(parsed.keys())}")
                return parsed
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing failed at position {e.pos}: {e.msg}")
                logger.error(f"Context around error: {cleaned_text[max(0, e.pos-100):e.pos+100]}")
                logger.warning(f"Expected JSON output but parsing failed: {e}, returning raw text")
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

        # 5. Get provider with specific model (generic!)
        provider = self._get_provider(config['provider'], config.get('model'))

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
        provider = self._get_provider(config['provider'], config.get('model'))

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
        provider = self._get_provider(config['provider'], config.get('model'))

        logger.info(f"Calling {config['provider']} for {template_name}")
        response = self._call_provider(provider, prompt, config)

        result = self._parse_response(response, template)
        return result.get('response', response) if isinstance(result, dict) else result
