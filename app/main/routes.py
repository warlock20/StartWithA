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

from flask import redirect, url_for, flash, render_template, jsonify
from flask_login import login_required, current_user
from app.main import bp # Assuming your blueprint is 'bp'

@bp.route('/health')
def health_check():
    """Health check endpoint for Railway/load balancers"""
    return jsonify({"status": "healthy", "service": "investment-platform"}), 200

@bp.route('/') # 'bp' is your main blueprint instance
def index():
    # If the user is logged in, redirect them to their dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    # If the user is a visitor (not logged in), show them the new public homepage
    # No explicit title → falls back to APP_NAME (brand) in the base template
    return render_template('main/public_home.html')


@bp.route('/legal/imprint')
def imprint():
    return render_template('main/legal/imprint.html', title="Imprint / Impressum")

@bp.route('/legal/privacy')
def privacy():
    return render_template('main/legal/privacy.html', title="Privacy Policy")

@bp.route('/legal/terms')
def terms():
    return render_template('main/legal/terms.html', title="Terms of Use")

@bp.route('/legal/cookies')
def cookies():
    return render_template('main/legal/cookies.html', title="Cookie Policy")
                                                                                                 
