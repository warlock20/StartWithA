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

import logging

from flask import Blueprint, flash, render_template, redirect, request, url_for
from flask_login import login_required, current_user

from app.services.capital_timing import (
    GRADUAL, LUMP_SUM, imported_capital_mode, switch_imported_capital,
)
from app.services.config_service import ConfigService
from app.services.currency_service import CurrencyService
from app.services.monitor_registry import get_monitor
from app.services.monitor_schedule import MonitorSettingError, monitor_rows, run_now, update_setting
from app.services.portfolio_analytics_metrics import build_portfolio_analytics

logger = logging.getLogger(__name__)

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
        capital_mode=imported_capital_mode(current_user.id),
    )


@settings_bp.route('/preferences/capital-timing', methods=['POST'])
@login_required
def update_capital_timing():
    """Re-date the auto-calculated imported capital."""
    mode = request.form.get('capital_timing')
    if mode not in (GRADUAL, LUMP_SUM):
        flash('Choose how the imported capital came in.', 'danger')
        return redirect(url_for('settings.preferences'))

    if not switch_imported_capital(current_user.id, mode):
        flash('No imported capital to update.', 'info')
        return redirect(url_for('settings.preferences'))

    try:
        xirr = build_portfolio_analytics(current_user.id)['kpis']['xirr']
    except Exception:
        logger.exception('XIRR for the capital timing flash failed')
        xirr = None
    if xirr is None:
        flash('Imported capital updated.', 'success')
    else:
        flash(f'Imported capital updated. Annualized return: {xirr}%', 'success')
    return redirect(url_for('settings.preferences'))


@settings_bp.route('/privacy')
@login_required
def privacy():
    """Data export and account deletion."""
    return render_template('settings_privacy.html', active_section='privacy')


@settings_bp.route('/monitors')
@login_required
def monitors():
    """Background AI: scheduled monitors, with the checks that fire on events."""
    return render_template(
        'settings_monitors.html',
        active_section='monitors',
        section_title='Background AI',
        section_intro=('AI checks that run on a schedule or when you do something. '
                       'Each run uses AI tokens from your monthly budget.'),
        monitors=monitor_rows(current_user),
        ai_consent=current_user.ai_consent_given,
    )


@settings_bp.route('/monitors/<key>', methods=['POST'])
@login_required
def update_monitor(key):
    """Save one monitor's on/off and frequency."""
    enabled = request.form.get('enabled') == 'on'
    frequency = request.form.get('frequency', '')
    try:
        update_setting(current_user, key, enabled, frequency)
    except MonitorSettingError as error:
        flash(str(error), 'danger')
    else:
        label = get_monitor(key).label
        flash(f'{label}: {"on, " + frequency if enabled else "off"}.', 'success')
    return redirect(url_for('settings.monitors', _anchor=f'monitor-{key}'))


@settings_bp.route('/monitors/<key>/run', methods=['POST'])
@login_required
def run_monitor_now(key):
    """Queue a monitor run now, outside its schedule."""
    try:
        run_now(current_user, key)
    except MonitorSettingError as error:
        flash(str(error), 'danger')
    else:
        flash(f'{get_monitor(key).label} queued. Refresh in a minute to see the result.', 'success')
    return redirect(url_for('settings.monitors', _anchor=f'monitor-{key}'))
