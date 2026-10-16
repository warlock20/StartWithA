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
Utility decorators for the investment checklist platform.
"""

from functools import wraps
from flask import current_app, jsonify, redirect, url_for, flash, request
from flask_login import current_user
from werkzeug.exceptions import HTTPException
from app import db
from app.features import user_has_feature
from app.utils.response_utils import json_error

GENERIC_ERROR_MESSAGE = 'Something went wrong. Please try again.'


def json_errors(view_or_message=None):
    """
    Turn an unexpected exception in a JSON route into a logged, generic 500.

    Rolls back the session, logs the traceback with the request path, and
    returns json_error(message, 500), so exception text never reaches the
    client. HTTP errors (abort(403), get_or_404) pass through untouched.

    Usage:
        @bp.route('/api/thing', methods=['POST'])
        @login_required
        @json_errors
        def thing(): ...

        @json_errors('Failed to save note. Please try again.')
        def save_note(): ...
    """
    message = view_or_message if isinstance(view_or_message, str) else GENERIC_ERROR_MESSAGE

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except HTTPException:
                raise
            except Exception:
                db.session.rollback()
                current_app.logger.exception('Unhandled error in %s %s', request.method, request.path)
                return json_error(message, status_code=500)

        return decorated_function

    return decorator(view_or_message) if callable(view_or_message) else decorator


def require_ai_tokens(tokens_needed=5000):
    """
    Decorator to enforce AI token limits before executing a route.

    Checks if the current user has enough tokens available. If not, returns
    a 429 (Too Many Requests) error with details about token usage.

    Args:
        tokens_needed: Number of tokens required for this operation (default 5000)

    Usage:
        @research_bp.route('/ai_assist', methods=['POST'])
        @login_required
        @require_ai_tokens(5000)
        def ai_assist():
            # Your route logic here
            pass

    Returns:
        If insufficient tokens: JSON response with error and 429 status
        If sufficient tokens: Proceeds to wrapped function
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if user is authenticated
            if not current_user.is_authenticated:
                return jsonify({
                    'error': 'Authentication required',
                    'success': False
                }), 401

            # Check token availability
            if not current_user.can_use_ai_tokens(tokens_needed):
                tokens_remaining = current_user.get_tokens_remaining()
                reset_date = current_user.ai_tokens_reset_date

                return jsonify({
                    'error': 'AI token limit reached',
                    'success': False,
                    'tokens_needed': tokens_needed,
                    'tokens_remaining': tokens_remaining,
                    'tokens_used': current_user.ai_tokens_used,
                    'tokens_limit': current_user.ai_tokens_limit,
                    'reset_date': reset_date.isoformat() if reset_date else None,
                    'message': f'You have used {current_user.ai_tokens_used} of {current_user.ai_tokens_limit} tokens. Your limit resets on {reset_date.strftime("%Y-%m-%d") if reset_date else "unknown date"}.'
                }), 429

            # User has enough tokens - proceed with request
            return f(*args, **kwargs)

        return decorated_function
    return decorator


def require_feature(feature_name):
    """
    Decorator to gate routes behind the feature tier system.

    For page requests: redirects to dashboard with a flash message.
    For API/AJAX requests: returns 403 JSON.

    Usage:
        @bp.route('/intelligence')
        @login_required
        @require_feature('portfolio_intelligence')
        def intelligence_hub():
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Authentication required', 'success': False}), 401

            if not user_has_feature(current_user, feature_name):
                # API/AJAX requests get JSON
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'error': 'Feature not available',
                        'feature': feature_name,
                        'success': False
                    }), 403

                # Page requests get redirected
                flash('This feature is not available on your current plan.', 'info')
                return redirect(url_for('portfolio.dashboard'))

            return f(*args, **kwargs)

        return decorated_function
    return decorator
