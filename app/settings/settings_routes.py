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
Settings Hub Routes

The account, preferences and data & privacy sections of the settings area.
Investor Profile (profile_routes) and AI (ai_model_routes) render into the
same sidebar layout from their own blueprints.
"""

from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

from app.services.config_service import ConfigService
from app.services.currency_service import CurrencyService

settings_bp = Blueprint('settings', __name__, url_prefix='/settings', template_folder='templates')


@settings_bp.route('/')
@login_required
def index():
    return redirect(url_for('settings.account'))


@settings_bp.route('/account')
@login_required
def account():
    """Who you are, your plan and AI usage, and a summary of your setup."""
    return render_template(
        'settings_account.html',
        active_section='account',
        user_profile_info=ConfigService.get_user_profile_info(current_user.id),
    )


@settings_bp.route('/preferences')
@login_required
def preferences():
    """Display currency and feature visibility."""
    return render_template(
        'settings_preferences.html',
        active_section='preferences',
        currencies=CurrencyService.get_supported_currencies(),
    )


@settings_bp.route('/privacy')
@login_required
def privacy():
    """Data export and account deletion."""
    return render_template('settings_privacy.html', active_section='privacy')
