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
AI Model Settings Routes

Allows users to select which AI model to use for each prompt category.
Overrides are stored in the UserAIPreference table and take priority over
YAML defaults and task-based routing.
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
import logging

from app import db
from app.models.user_ai_preferences import UserAIPreference
from app.services.ai.config import AIModel, AIProvider, get_ai_config
from app.services.ai.prompt_service import prompt_service

logger = logging.getLogger(__name__)

ai_model_bp = Blueprint(
    'ai_models', __name__,
    url_prefix='/settings/ai-models',
    template_folder='templates',
)

# Display-friendly names for prompt categories
CATEGORY_LABELS = {
    'screening': 'Kill Checklist Screening',
    'research': 'Research Analysis',
    'research_journal': 'Research Journal',
    'companion': 'Research Companion',
    'checkpoint': 'Checkpoint Analysis',
    'intelligence': 'AI Intelligence',
    'portfolio': 'Portfolio Analytics',
    'competitor_analysis': 'Competitor Analysis',
    'argos': 'Argos Insights',
    'document_processing': 'Document Processing',
}

CATEGORY_ICONS = {
    'screening': 'bi-funnel',
    'research': 'bi-search',
    'research_journal': 'bi-journal-text',
    'companion': 'bi-chat-dots',
    'checkpoint': 'bi-flag',
    'intelligence': 'bi-lightbulb',
    'portfolio': 'bi-pie-chart',
    'competitor_analysis': 'bi-people',
    'argos': 'bi-eye',
    'document_processing': 'bi-file-earmark-text',
}


def _get_available_models():
    """Build the list of models available for selection, grouped by provider."""
    config = get_ai_config()
    models = []

    # Gemini models
    if config.is_provider_available(AIProvider.GEMINI):
        models.extend([
            {'id': 'gemini-3-flash-preview', 'name': 'Gemini 3 Flash (Preview)', 'provider': 'gemini'},
            {'id': 'gemini-3-pro-preview', 'name': 'Gemini 3 Pro (Preview)', 'provider': 'gemini'},
            {'id': 'gemini-2.5-flash', 'name': 'Gemini 2.5 Flash', 'provider': 'gemini'},
            {'id': 'gemini-2.5-pro', 'name': 'Gemini 2.5 Pro', 'provider': 'gemini'},
        ])

    # Claude models
    if config.is_provider_available(AIProvider.CLAUDE):
        models.extend([
            {'id': 'claude-sonnet-4-20250514', 'name': 'Claude Sonnet 4', 'provider': 'claude'},
            {'id': 'claude-opus-4-20250514', 'name': 'Claude Opus 4', 'provider': 'claude'},
            {'id': 'claude-3-5-haiku-20241022', 'name': 'Claude 3.5 Haiku', 'provider': 'claude'},
        ])

    # DeepSeek models
    if config.is_provider_available(AIProvider.DEEPSEEK):
        models.extend([
            {'id': 'deepseek-chat', 'name': 'DeepSeek V3', 'provider': 'deepseek'},
            {'id': 'deepseek-reasoner', 'name': 'DeepSeek R1 (Reasoning)', 'provider': 'deepseek'},
        ])

    return models


def _get_categories_with_defaults():
    """Get all prompt categories with their YAML default model/provider."""
    categories = []
    all_prompts = prompt_service.list_all_prompts()

    for category, prompt_names in sorted(all_prompts.items()):
        # Use the first prompt in the category to get default model info
        try:
            info = prompt_service.get_prompt_info(category, prompt_names[0])
        except (ValueError, IndexError):
            continue

        categories.append({
            'name': category,
            'label': CATEGORY_LABELS.get(category, category.replace('_', ' ').title()),
            'icon': CATEGORY_ICONS.get(category, 'bi-gear'),
            'default_model': info.get('model'),
            'default_provider': info.get('preferred_provider'),
            'prompt_count': len(prompt_names),
        })

    return categories


@ai_model_bp.route('/')
@login_required
def ai_model_settings():
    """Main AI model settings page."""
    categories = _get_categories_with_defaults()
    available_models = _get_available_models()
    user_prefs = UserAIPreference.get_user_preferences(current_user.id)

    # Merge user overrides into category data
    for cat in categories:
        pref = user_prefs.get(cat['name'])
        if pref:
            cat['user_model'] = pref.model_override
            cat['user_provider'] = pref.provider_override
        else:
            cat['user_model'] = None
            cat['user_provider'] = None

    override_count = sum(1 for c in categories if c['user_model'])

    return render_template(
        'ai_model_settings.html',
        categories=categories,
        available_models=available_models,
        override_count=override_count,
    )


@ai_model_bp.route('/set', methods=['POST'])
@login_required
def set_model_preference():
    """Set a model override for a prompt category."""
    category = request.form.get('category')
    model_id = request.form.get('model_id')

    if not category:
        flash('Invalid category', 'error')
        return redirect(url_for('ai_models.ai_model_settings'))

    if not model_id or model_id == 'default':
        # Clear the override
        UserAIPreference.clear_preference(current_user.id, category)
        db.session.commit()
        flash(f'Reset {CATEGORY_LABELS.get(category, category)} to default', 'success')
        return redirect(url_for('ai_models.ai_model_settings'))

    # Resolve model to get provider
    try:
        model_enum = AIModel.from_string(model_id)
        provider_str = model_enum.provider.value
    except (ValueError, KeyError):
        flash(f'Unknown model: {model_id}', 'error')
        return redirect(url_for('ai_models.ai_model_settings'))

    UserAIPreference.set_preference(
        user_id=current_user.id,
        prompt_category=category,
        model_override=model_id,
        provider_override=provider_str,
    )
    db.session.commit()

    model_name = model_id
    for m in _get_available_models():
        if m['id'] == model_id:
            model_name = m['name']
            break

    flash(f'{CATEGORY_LABELS.get(category, category)} set to {model_name}', 'success')
    return redirect(url_for('ai_models.ai_model_settings'))


@ai_model_bp.route('/reset-all', methods=['POST'])
@login_required
def reset_all_model_preferences():
    """Reset all model overrides to defaults."""
    prefs = UserAIPreference.query.filter_by(user_id=current_user.id).all()
    for pref in prefs:
        db.session.delete(pref)
    db.session.commit()
    flash('All AI model preferences reset to defaults', 'success')
    return redirect(url_for('ai_models.ai_model_settings'))


# ============================================
# API ENDPOINTS (for AJAX)
# ============================================

@ai_model_bp.route('/api/preferences')
@login_required
def api_get_preferences():
    """Get user's current AI model preferences."""
    prefs = UserAIPreference.get_user_preferences(current_user.id)
    return jsonify({
        'preferences': {k: v.to_dict() for k, v in prefs.items()}
    })


@ai_model_bp.route('/api/set', methods=['POST'])
@login_required
def api_set_preference():
    """API endpoint to set a model preference."""
    data = request.get_json()
    category = data.get('category')
    model_id = data.get('model_id')

    if not category:
        return jsonify({'success': False, 'error': 'Missing category'}), 400

    if not model_id or model_id == 'default':
        UserAIPreference.clear_preference(current_user.id, category)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Reset to default'})

    try:
        model_enum = AIModel.from_string(model_id)
        provider_str = model_enum.provider.value
    except (ValueError, KeyError):
        return jsonify({'success': False, 'error': f'Unknown model: {model_id}'}), 400

    UserAIPreference.set_preference(
        user_id=current_user.id,
        prompt_category=category,
        model_override=model_id,
        provider_override=provider_str,
    )
    db.session.commit()
    return jsonify({'success': True, 'category': category, 'model_id': model_id})


@ai_model_bp.route('/api/available-models')
@login_required
def api_available_models():
    """Get list of available models."""
    return jsonify({'models': _get_available_models()})
