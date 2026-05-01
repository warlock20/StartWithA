from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, current_user, logout_user, login_required
from app import db, limiter
from app.models import User
from app.auth import auth_bp # Import the blueprint from this package's __init__.py
from app.constants import RATELIMIT_AUTH
from app.utils.audit_logger import log_auth_event
from app.services.feature_unlock_service import FeatureUnlockService


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit(RATELIMIT_AUTH)
def login():
    if current_user.is_authenticated: # If user is already logged in, redirect them
        flash('You are already logged in.', 'info')
        return redirect(url_for('research_workflow.my_projects')) # Or a dashboard page

    if request.method == 'POST':
        identifier = request.form.get('identifier') # Can be username or email
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False # Check for "remember me"

        if not identifier or not password:
            flash('Both username/email and password are required.', 'error')
            return render_template('login.html', title="Login")

        # Try to find user by username or email
        user_by_username = User.query.filter_by(username=identifier).first()
        user_by_email = User.query.filter_by(email=identifier).first()

        user = user_by_username or user_by_email

        if user and user.check_password(password):
            login_user(user, remember=remember) # Log in the user with Flask-Login
            log_auth_event(user.id, 'login')

            newly_unlocked = FeatureUnlockService.check_and_unlock(user)
            if newly_unlocked:
                names = ', '.join(n.replace('_', ' ').title() for n in newly_unlocked)
                flash(f'New features unlocked: {names}!', 'success')

            flash('Login successful!', 'success')

            # Redirect to the page the user was trying to access, or a default page
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            else:
                # Redirect to dashboard after login
                return redirect(url_for('dashboard.index')) 
        else:
            log_auth_event(None, 'failed_login')
            flash('Invalid username/email or password. Please try again.', 'error')
            return render_template('login.html', title="Login", identifier=identifier)

    # For GET request
    return render_template('login.html', title="Login")

@auth_bp.route('/logout')
@login_required
def logout():
    log_auth_event(current_user.id, 'logout')
    logout_user() # Flask-Login function to clear the user session
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login')) # Redirect to login page after logout

@auth_bp.route('/account')
@login_required
def account_settings():
    """Display user account settings page with basic information and account management"""
    # Get user statistics from various modules for dashboard-like view
    from app.journal_enhanced.utils import get_journal_statistics

    # Gather some basic stats to show in profile
    stats = {
        'total_companies': current_user.companies.count(),
        'total_research_projects': current_user.research_projects.count(),
        'total_ideas': current_user.idea_pipeline.count(),
        'total_checklists': current_user.checklists.count(),
    }

    # Get journal stats if available
    try:
        journal_stats = get_journal_statistics(current_user.id)
        stats.update({
            'total_journal_entries': journal_stats.get('total_entries', 0),
            'pending_reviews': journal_stats.get('pending_reviews', 0)
        })
    except:
        stats.update({
            'total_journal_entries': 0,
            'pending_reviews': 0
        })

    return render_template('account.html',
                         title="Account Settings",
                         user=current_user,
                         stats=stats)


@auth_bp.route('/update-settings', methods=['POST'])
@login_required
def update_settings():
    """Update user settings including base currency"""
    try:
        # Get form data
        base_currency = request.form.get('base_currency', 'USD').strip().upper()
        show_original_currency = request.form.get('show_original_currency') == 'on'

        # Validate currency code
        from app.services.currency_service import CurrencyService
        supported_currencies = [c['code'] for c in CurrencyService.get_supported_currencies()]

        if base_currency not in supported_currencies:
            flash(f'Invalid currency code: {base_currency}', 'error')
            return redirect(url_for('auth.account_settings'))

        # Check if currency is changing
        old_currency = current_user.base_currency
        currency_changed = (old_currency != base_currency)

        # Update user settings
        current_user.base_currency = base_currency
        current_user.show_original_currency = show_original_currency

        db.session.commit()

        # Show success message
        if currency_changed:
            flash(f'Base currency changed from {old_currency} to {base_currency}. Portfolio values will be recalculated.', 'success')
        else:
            flash('Settings updated successfully!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error updating settings: {str(e)}', 'error')

    return redirect(url_for('auth.account_settings'))


@auth_bp.route('/update-feature-preferences', methods=['POST'])
@login_required
def update_feature_preferences():
    """Toggle the show_advanced_features flag."""
    current_user.show_advanced_features = 'show_advanced_features' in request.form
    db.session.commit()
    flash('Feature preferences updated.', 'success')
    return redirect(url_for('auth.account_settings'))


@auth_bp.route('/dismiss-new-feature/<group_name>', methods=['POST'])
@login_required
def dismiss_new_feature(group_name):
    """Remove a feature group from the NEW badge state."""
    FeatureUnlockService.dismiss_new_badge(current_user, group_name)
    return '', 204
