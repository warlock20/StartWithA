"""
Utility decorators for the investment checklist platform.
"""

from functools import wraps
from flask import jsonify
from flask_login import current_user


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
