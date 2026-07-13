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
Auth0 authentication routes for OAuth-based login
Supports email/password via Auth0 Universal Login and social providers (Google, GitHub, etc.)
"""

from flask import redirect, session, url_for, flash, current_app, request, abort
from flask_login import login_user, logout_user, current_user
from authlib.integrations.flask_client import OAuth
from urllib.parse import urlencode
from app import db
from app.utils.audit_logger import log_auth_event
from app.models import User
from app.auth import auth_bp
from app.utils.auth_utils import is_authorized
from app.services.feature_unlock_service import FeatureUnlockService
import secrets


# Initialize OAuth
oauth = OAuth()


def init_auth0(app):
    """Initialize Auth0 OAuth client with Flask app"""
    oauth.init_app(app)

    oauth.register(
        "auth0",
        client_id=app.config["AUTH0_CLIENT_ID"],
        client_secret=app.config["AUTH0_CLIENT_SECRET"],
        client_kwargs={
            "scope": "openid profile email",
        },
        server_metadata_url=f'https://{app.config["AUTH0_DOMAIN"]}/.well-known/openid-configuration',
    )


@auth_bp.route("/auth0-login")
def auth0_login():
    """Redirect user to Auth0 Universal Login page"""
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('dashboard.index'))

    if not current_app.config.get('AUTH0_CONFIGURED'):
        flash('Auth0 is not configured. Please use email/password login.', 'warning')
        return redirect(url_for('auth.login'))

    # Generate and store state for CSRF protection
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state

    return oauth.auth0.authorize_redirect(
        redirect_uri=current_app.config["AUTH0_CALLBACK_URL"],
        state=state
    )


@auth_bp.route("/callback")
def auth0_callback():
    """
    Auth0 callback route - handles the redirect after successful Auth0 authentication.
    Creates or updates user in database and logs them in via Flask-Login.
    """
    try:
        # Verify state for CSRF protection
        if 'oauth_state' not in session or request.args.get('state') != session['oauth_state']:
            flash('Invalid authentication state. Please try again.', 'error')
            return redirect(url_for('auth.login'))

        # Get the token from Auth0
        token = oauth.auth0.authorize_access_token()

        # Get user info from Auth0
        userinfo = token.get('userinfo')

        if not userinfo:
            flash('Failed to get user information from Auth0.', 'error')
            return redirect(url_for('auth.login'))

        # Check if user is authorized (allowlist)
        if not is_authorized(userinfo.get('email')):
            flash("This is currently a private beta. Please contact the admin for access.", "warning")
            return redirect(url_for('main.public_home'))
        
        # Extract user data
        auth0_id = userinfo['sub']  # Unique Auth0 user ID (e.g., "auth0|123", "google-oauth2|456")
        email = userinfo.get('email')
        name = userinfo.get('name')
        picture = userinfo.get('picture')

        # Determine auth provider from auth0_id
        auth_provider = auth0_id.split('|')[0] if '|' in auth0_id else 'auth0'

        # Check if user exists by auth0_id
        user = User.query.filter_by(auth0_id=auth0_id).first()

        if not user and email:
            # Check if user exists by email (for linking existing accounts)
            user = User.query.filter_by(email=email).first()

        if user:
            # Update existing user's Auth0 info
            user.auth0_id = auth0_id
            user.name = name
            user.picture = picture
            user.auth_provider = auth_provider
            if email and not user.email:
                user.email = email

            db.session.commit()
            flash('Welcome back!', 'success')
        else:
            # Create new user
            if not email:
                flash('Email is required to create an account.', 'error')
                return redirect(url_for('auth.login'))

            # Generate username from email or name
            username = email.split('@')[0] if email else name.replace(' ', '').lower()

            # Ensure username is unique
            base_username = username
            counter = 1
            while User.query.filter_by(username=username).first():
                username = f"{base_username}{counter}"
                counter += 1

            user = User(
                auth0_id=auth0_id,
                username=username,
                email=email,
                name=name,
                picture=picture,
                auth_provider=auth_provider,
                subscription_tier=current_app.config.get('DEFAULT_USER_TIER', 'amateur')
            )

            db.session.add(user)
            db.session.commit()
            flash('Account created successfully! Welcome to Investment Checklist.', 'success')

        # Log in the user with Flask-Login
        login_user(user, remember=True)
        log_auth_event(user.id, 'login_auth0')

        newly_unlocked = FeatureUnlockService.check_and_unlock(user)
        if newly_unlocked:
            names = ', '.join(n.replace('_', ' ').title() for n in newly_unlocked)
            flash(f'New features unlocked: {names}!', 'success')

        # Clear OAuth state from session
        session.pop('oauth_state', None)

        # Redirect to dashboard
        return redirect(url_for('dashboard.index'))

    except Exception as e:
        current_app.logger.error(f"Auth0 callback error: {str(e)}")
        flash('Authentication failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))


@auth_bp.route("/auth0-logout")
def auth0_logout():
    """Logout user from both Flask-Login and Auth0"""
    # Clear Flask-Login session
    if current_user.is_authenticated:
        log_auth_event(current_user.id, 'logout_auth0')
    logout_user()

    # Clear Flask session
    session.clear()

    # Local-only logout when Auth0 is not configured
    if not current_app.config.get('AUTH0_CONFIGURED'):
        flash('You have been logged out.', 'success')
        return redirect(url_for('auth.login'))

    # Build Auth0 logout URL
    params = {
        'returnTo': url_for('auth.login', _external=True),
        'client_id': current_app.config["AUTH0_CLIENT_ID"]
    }

    # Redirect to Auth0 logout (this also logs user out of Auth0 session)
    auth0_logout_url = f'https://{current_app.config["AUTH0_DOMAIN"]}/v2/logout?{urlencode(params)}'

    flash('You have been logged out.', 'success')
    return redirect(auth0_logout_url)
