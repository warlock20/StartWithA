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

"""Which model runs each AI check stage: stage capabilities, presets, the user's own setup."""

from app.models import ResearchSettings
from app.models.user_ai_preferences import UserAIPreference
from app.services.ai.config import MODEL_TIERS, AIProvider, get_ai_config, resolve_model_name
from app.services.ai.prompt_service import prompt_service
from app.services.ai_check import AICheckError
from app.services.ai_check.pricing import provider_of

# 'quick' is the Quick check's single call (spec §10.2); a full run uses the other three.
STAGES = ('gather', 'extract', 'analyze', 'quick')
STAGE_TITLES = {'gather': 'Gather', 'extract': 'Extract', 'analyze': 'Analyze', 'quick': 'Quick check'}
STAGE_PROMPTS = {'gather': 'ai_check_gather', 'extract': 'ai_check_extract', 'analyze': 'ai_check_analyze',
                 'quick': 'ai_check_quick'}
MY_SETUP = 'my_setup'
PREF_PREFIX = 'ai_check:'
# Runs created before model choice existed ran on these.
LEGACY_MODELS = {'gather': 'claude-sonnet-5', 'extract': 'claude-sonnet-5', 'analyze': 'claude-opus-5',
                 'quick': 'claude-sonnet-5'}

# Gather needs web search and function tools in one call: Claude, Gemini 3 or Gemini 4 (not 2.5).
_SEARCHERS = ('claude-sonnet-5', 'claude-opus-5', 'gemini-3-flash-preview', 'gemini-3.1-pro-preview',
              'gemini-4-argon', 'gemini-3.8-flash')
# gemini-3.5-flash-lite: search plus functions unconfirmed, so it reads but doesn't gather.
_READERS = _SEARCHERS + ('gemini-3.5-flash-lite', 'gemini-2.5-flash', 'gemini-2.5-pro', 'deepseek-flash', 'deepseek-v4-pro')
# Quick may search and read documents in the same call, so it needs what Gather needs.
STAGE_MODELS = {'gather': _SEARCHERS, 'extract': _READERS, 'analyze': _READERS, 'quick': _SEARCHERS}
STAGE_RULES = {
    'gather': 'Gather searches the web, so it needs Claude, Gemini 3 or Gemini 4.',
    'quick': 'The Quick check may search the web, so it needs Claude, Gemini 3 or Gemini 4.',
    'extract': 'Extract needs a Claude, Gemini or DeepSeek V4 model.',
    'analyze': 'Analyze needs a Claude, Gemini or DeepSeek V4 model.',
}
TEXT_ONLY = {'deepseek-flash', 'deepseek-v4-pro'}  # reads PDF text without layout
MODEL_LABELS = {
    'claude-sonnet-5': 'Claude Sonnet 5', 'claude-opus-5': 'Claude Opus 5',
    'gemini-3-flash-preview': 'Gemini 3 Flash (Legacy)', 'gemini-3.1-pro-preview': 'Gemini 3.1 Pro',
    'gemini-4-argon': 'Gemini 4 Argon', 'gemini-3.8-flash': 'Gemini 3.8 Flash',
    'gemini-3.5-flash-lite': 'Gemini 3.5 Flash Lite',
    'gemini-2.5-flash': 'Gemini 2.5 Flash', 'gemini-2.5-pro': 'Gemini 2.5 Pro',
    'deepseek-flash': 'DeepSeek V4 Flash', 'deepseek-v4-pro': 'DeepSeek V4 Pro',
}
# Web searches per run (ResearchSettings.ai_check_search_budget), frozen on run.models at start.
DEFAULT_SEARCH_BUDGET = 5
MIN_SEARCH_BUDGET, MAX_SEARCH_BUDGET = 1, 10
PROVIDER_NAMES = {'claude': 'Claude', 'gemini': 'Gemini', 'deepseek': 'DeepSeek'}
# Old or alternative spellings users may have saved.
_ALIASES = {'deepseek-chat': 'deepseek-flash', 'deepseek-reasoner': 'deepseek-flash',
            'deepseek-v4-flash': 'deepseek-flash'}


def canonical(name):
    """Exact model id for a saved or YAML model name. AIModel.from_string is not used here: it
    silently returns the default Flash for names it doesn't know."""
    key = (name or '').strip().lower()
    if key in MODEL_TIERS:
        return resolve_model_name(key).model_id
    return _ALIASES.get(key, key)


def model_label(model_id):
    return MODEL_LABELS.get(model_id, model_id)


def provider_ready(model_id):
    provider = provider_of(model_id)
    return bool(provider) and get_ai_config().is_provider_available(AIProvider(provider))


def presets():
    return prompt_service.get_prompt_data('research', 'ai_check_presets').get('presets') or {}


def stage_default(stage):
    return canonical(prompt_service.get_prompt_data('research', STAGE_PROMPTS[stage]).get('model'))


def my_setup_choice(user_id, stage):
    pref = UserAIPreference.get_preference(user_id, PREF_PREFIX + stage)
    return pref.model_override if pref and pref.model_override else None


def check_stage_model(stage, name):
    """The canonical model id if it can run `stage` and its provider is configured."""
    model_id = canonical(name)
    if model_id not in STAGE_MODELS[stage]:
        raise AICheckError(f"{model_label(model_id) or 'That model'} can't run {STAGE_TITLES[stage]}. "
                           f'{STAGE_RULES[stage]}')
    if not provider_ready(model_id):
        raise AICheckError(f'{PROVIDER_NAMES[provider_of(model_id)]} is not configured on the server.')
    return model_id


def resolve_setup(user_id, choice=None):
    """Per-stage models for a new run: {'setup', 'label', 'gather', 'extract', 'analyze'}.
    The per-category override for 'research' is deliberately never read here."""
    choice = choice or MY_SETUP
    if choice == MY_SETUP:
        label = 'My setup'
        raw = {stage: my_setup_choice(user_id, stage) or stage_default(stage) for stage in STAGES}
    else:
        preset = presets().get(choice)
        if not preset:
            raise AICheckError('Unknown model setup.')
        label = preset.get('label') or choice
        raw = {stage: preset.get(stage) for stage in STAGES}
    return {'setup': choice, 'label': label,
            **{stage: check_stage_model(stage, raw[stage]) for stage in STAGES}}


def _summary(key, label, models):
    return {'key': key, 'label': label, 'models': models,
            'labels': {stage: model_label(model) for stage, model in models.items()}}


def available_setups(user_id):
    """Setups that resolve right now: My setup first, then presets in YAML order."""
    setups = []
    for key in [MY_SETUP, *presets()]:
        try:
            resolved = resolve_setup(user_id, key)
        except AICheckError:
            continue
        setups.append(_summary(key, resolved['label'], {stage: resolved[stage] for stage in STAGES}))
    return setups


def ai_check_available(user_id):
    return bool(available_setups(user_id))


def user_search_budget(user_id):
    settings = ResearchSettings.query.filter_by(user_id=user_id).first()
    return settings.ai_check_search_budget if settings and settings.ai_check_search_budget else DEFAULT_SEARCH_BUDGET


def run_search_budget(run):
    """The run's frozen search budget; runs started before the setting existed get the default."""
    return (run.models or {}).get('search_budget') or DEFAULT_SEARCH_BUDGET


def stage_model(run, stage):
    return (run.models or {}).get(stage) or LEGACY_MODELS[stage]


def setup_summary(run):
    models = run.models or {}
    return _summary(models.get('setup'), models.get('label') or 'Claude (before model choice)',
                    {stage: stage_model(run, stage) for stage in STAGES})


def stage_options(stage):
    """Models the settings page offers for a stage: capable ones whose provider is configured."""
    return [{'id': model, 'label': model_label(model), 'text_only': model in TEXT_ONLY}
            for model in STAGE_MODELS[stage] if provider_ready(model)]
