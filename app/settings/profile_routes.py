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
Profile Settings Routes

Routes for user investment profile selection and configuration customization.

Add these routes to your settings blueprint or create a new one.
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
import logging

from app import db
from app.services.config_service import ConfigService

logger = logging.getLogger(__name__)

# Create blueprint (or add to existing settings blueprint)
profile_bp = Blueprint('profile', __name__, url_prefix='/settings/profile', template_folder='templates')


# ============================================
# PROFILE SELECTION PAGE
# ============================================

@profile_bp.route('/')
@login_required
def profile_settings():
    """
    Main profile settings page.
    User can select investor profile and customize settings.
    """
    # Get available profiles
    profiles = ConfigService.get_available_profiles()
    
    # Get user's current profile info
    user_profile_info = ConfigService.get_user_profile_info(current_user.id)
    
    # Get all configs grouped by category (for customization)
    configs_by_category = ConfigService.get_configs_by_category()
    
    # Get user's effective config values
    user_config = ConfigService.get_user_config(current_user.id)
    
    return render_template(
        'profile_settings.html',
        profiles=profiles,
        user_profile_info=user_profile_info,
        configs_by_category=configs_by_category,
        user_config=user_config
    )


@profile_bp.route('/select', methods=['POST'])
@login_required
def select_profile():
    """
    Select an investor profile.
    """
    profile_name = request.form.get('profile_name')
    
    if not profile_name:
        flash('Please select a profile', 'error')
        return redirect(url_for('profile.profile_settings'))
    
    try:
        ConfigService.set_user_profile(current_user.id, profile_name)
        flash(f'Profile updated to {profile_name.title()}!', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    
    return redirect(url_for('profile.profile_settings'))


@profile_bp.route('/customize', methods=['POST'])
@login_required
def customize_setting():
    """
    Set a custom override for a specific setting.
    """
    key = request.form.get('key')
    value = request.form.get('value')
    
    if not key or value is None:
        flash('Invalid setting', 'error')
        return redirect(url_for('profile.profile_settings'))
    
    try:
        # Convert value to appropriate type
        value = _parse_value(value)
        ConfigService.set_custom_override(current_user.id, key, value)
        flash('Setting customized!', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    
    return redirect(url_for('profile.profile_settings'))


@profile_bp.route('/reset-custom/<key>', methods=['POST'])
@login_required
def reset_custom_setting(key):
    """
    Remove a custom override for a specific setting.
    """
    ConfigService.remove_custom_override(current_user.id, key)
    flash('Setting reset to profile default', 'success')
    return redirect(url_for('profile.profile_settings'))


@profile_bp.route('/reset-all', methods=['POST'])
@login_required
def reset_all_custom():
    """
    Reset all custom overrides to profile defaults.
    """
    ConfigService.reset_to_profile_defaults(current_user.id)
    flash('All settings reset to profile defaults', 'success')
    return redirect(url_for('profile.profile_settings'))


# ============================================
# API ENDPOINTS (for AJAX)
# ============================================

@profile_bp.route('/api/profiles')
@login_required
def api_get_profiles():
    """Get available profiles."""
    profiles = ConfigService.get_available_profiles()
    return jsonify({'profiles': profiles})


@profile_bp.route('/api/current')
@login_required
def api_get_current_profile():
    """Get user's current profile and config."""
    profile_info = ConfigService.get_user_profile_info(current_user.id)
    config = ConfigService.get_user_config(current_user.id)
    
    return jsonify({
        'profile_info': profile_info,
        'config': config
    })


@profile_bp.route('/api/select', methods=['POST'])
@login_required
def api_select_profile():
    """API endpoint to select profile."""
    data = request.get_json()
    profile_name = data.get('profile_name')
    
    try:
        ConfigService.set_user_profile(current_user.id, profile_name)
        return jsonify({
            'success': True,
            'message': f'Profile updated to {profile_name}'
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@profile_bp.route('/api/customize', methods=['POST'])
@login_required
def api_customize_setting():
    """API endpoint to customize a setting."""
    data = request.get_json()
    key = data.get('key')
    value = data.get('value')
    
    try:
        ConfigService.set_custom_override(current_user.id, key, value)
        return jsonify({
            'success': True,
            'key': key,
            'value': value
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@profile_bp.route('/api/config/<key>')
@login_required
def api_get_config_with_metadata(key):
    """Get a config value with its metadata."""
    config = ConfigService.get_with_metadata(key, current_user.id)
    return jsonify(config)


# ============================================
# HELPERS
# ============================================

def _parse_value(value_str: str):
    """Parse string value to appropriate type."""
    # Try int first
    try:
        return int(value_str)
    except ValueError:
        pass
    
    # Try float
    try:
        return float(value_str)
    except ValueError:
        pass
    
    # Boolean
    if value_str.lower() in ('true', 'yes', '1'):
        return True
    if value_str.lower() in ('false', 'no', '0'):
        return False
    
    # Return as string
    return value_str
