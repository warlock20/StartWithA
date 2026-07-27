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
Admin Dashboard

Flask-Admin based admin interface for managing:
- System configuration
- Investor profiles
- Prompt versions
- Analytics
"""

import os

from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_login import current_user
from flask import flash, redirect, url_for, request

from app import db
from app.models import (
    SystemConfig,
    InvestorProfile,
    UserInvestmentProfile,
    PromptVersion,
    PromptUsageLog,
    User,
    AIResearchFeedback,
    MarketSweep,
    MarketSweepCompany,
)
from app.services.market_sweep_service import parse_companies_file


class SecureAdminIndexView(AdminIndexView):
    """Admin index page — requires is_admin."""
    @expose('/')
    def index(self):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        if not current_user.is_admin:
            return redirect(url_for('portfolio.dashboard'))
        return super().index()


class SecureModelView(ModelView):
    """
    Base ModelView that requires admin authentication.
    """
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin

    def inaccessible_callback(self, name, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        return redirect(url_for('portfolio.dashboard'))


class SystemConfigView(SecureModelView):
    """Admin view for SystemConfig"""
    column_list = ['key', 'value', 'category', 'data_type', 'description']
    column_searchable_list = ['key', 'category', 'description']
    column_filters = ['category', 'data_type']
    # Removed column_editable_list because 'value' is JSON field (not inline-editable)
    form_columns = ['key', 'value', 'description', 'category', 'data_type', 'min_value', 'max_value']

    can_create = True
    can_edit = True
    can_delete = False  # Don't allow deleting system configs

    page_size = 50


class InvestorProfileView(SecureModelView):
    """Admin view for InvestorProfile"""
    column_list = ['name', 'display_name', 'description', 'sort_order', 'is_active']
    column_searchable_list = ['name', 'display_name', 'description']
    column_filters = ['is_active']
    column_editable_list = ['sort_order', 'is_active']
    form_columns = ['name', 'display_name', 'description', 'icon', 'config_overrides', 'sort_order', 'is_active']

    can_create = True
    can_edit = True
    can_delete = False


class PromptVersionView(SecureModelView):
    """Admin view for PromptVersion"""
    column_list = ['name', 'version', 'category', 'is_active', 'is_default', 'preferred_provider', 'created_at']
    column_searchable_list = ['name', 'category', 'version', 'description']
    column_filters = ['category', 'is_active', 'is_default', 'preferred_provider']
    column_editable_list = ['is_active', 'is_default']
    column_default_sort = [('created_at', True)]

    form_columns = [
        'name', 'category', 'version', 'description',
        'template', 'system_context',
        'preferred_provider', 'model', 'max_tokens', 'temperature',
        'is_active', 'is_default',
        'created_by', 'notes'
    ]

    form_widget_args = {
        'template': {
            'rows': 15,
            'style': 'font-family: monospace;'
        },
        'system_context': {
            'rows': 5,
            'style': 'font-family: monospace;'
        },
        'description': {
            'rows': 3
        },
        'notes': {
            'rows': 3
        }
    }

    can_create = True
    can_edit = True
    can_delete = True

    page_size = 25


class PromptUsageLogView(SecureModelView):
    """Admin view for PromptUsageLog (Analytics)"""
    column_list = [
        'created_at', 'prompt_name', 'prompt_version', 'provider',
        'total_tokens', 'estimated_cost_cents', 'latency_ms', 'success'
    ]
    column_searchable_list = ['prompt_name', 'provider', 'model']
    column_filters = ['prompt_name', 'provider', 'success', 'created_at']
    column_default_sort = [('created_at', True)]

    can_create = False
    can_edit = False
    can_delete = True  # Allow cleanup of old logs

    page_size = 100

    # Add computed column for cost in dollars
    column_formatters = {
        'estimated_cost_cents': lambda v, c, m, p: f'${m.estimated_cost_dollars:.4f}' if m.estimated_cost_cents else '$0.00'
    }


class UserView(SecureModelView):
    """Admin view for User management and token monitoring"""
    column_list = [
        'id', 'email', 'username', 'subscription_tier',
        'show_advanced_features', 'unlocked_features',
        'ai_tokens_used', 'ai_tokens_limit', 'ai_tokens_reset_date',
        'auth_provider'
    ]
    column_searchable_list = ['email', 'username', 'auth0_id']
    column_filters = ['subscription_tier', 'auth_provider', 'show_advanced_features']
    column_editable_list = ['subscription_tier', 'ai_tokens_limit', 'show_advanced_features']
    column_default_sort = [('ai_tokens_used', True)]

    # Only show safe fields in edit form
    form_columns = [
        'email', 'username', 'name',
        'subscription_tier', 'show_advanced_features',
        'unlocked_features', 'newly_unlocked_features',
        'ai_tokens_limit', 'ai_tokens_used', 'ai_tokens_reset_date',
        'base_currency', 'preferred_sprint_duration', 'research_experience_level'
    ]

    can_create = False  # Users created via registration only
    can_edit = True
    can_delete = False  # Soft delete only

    page_size = 50

    # Format display values
    column_formatters = {
        'ai_tokens_used': lambda v, c, m, p: f'{m.ai_tokens_used:,}',
        'ai_tokens_limit': lambda v, c, m, p: f'{m.ai_tokens_limit:,}',
        'ai_tokens_reset_date': lambda v, c, m, p: m.ai_tokens_reset_date.strftime('%Y-%m-%d') if m.ai_tokens_reset_date else 'Not set'
    }

    column_descriptions = {
        'subscription_tier': 'User subscription level (amateur, beta_tester, pro)',
        'ai_tokens_used': 'Tokens used in current period',
        'ai_tokens_limit': 'Token limit per period',
        'ai_tokens_reset_date': 'When token usage resets'
    }


class AIResearchFeedbackView(SecureModelView):
    """Admin view for AI Research Assistant feedback and monitoring"""
    column_list = [
        'created_at', 'user_id', 'mode', 'feedback',
        'tokens_used', 'company_name', 'provider', 'model'
    ]
    column_searchable_list = ['company_name', 'question_text', 'user_answer']
    column_filters = ['mode', 'feedback', 'provider', 'model', 'created_at']
    column_default_sort = [('created_at', True)]

    # View-only for analytics
    can_create = False
    can_edit = False
    can_delete = True  # Allow cleanup

    page_size = 100

    # Format display
    column_formatters = {
        'tokens_used': lambda v, c, m, p: f'{m.tokens_used:,}' if m.tokens_used else 'N/A',
        'feedback': lambda v, c, m, p: m.feedback or 'No feedback yet'
    }

    column_descriptions = {
        'mode': 'AI mode used (challenge, elaboration, factcheck)',
        'feedback': 'User feedback (helpful, not_helpful, dismissed)',
        'tokens_used': 'Actual tokens consumed by this interaction'
    }


class MarketSweepAdminView(SecureModelView):
    """Admin view for MarketSweep with CSV/Excel upload support."""
    column_list = ['id', 'name', 'country', 'total_companies', 'is_active', 'created_at']
    column_searchable_list = ['name', 'country']
    column_filters = ['country', 'is_active']
    column_editable_list = ['is_active']
    form_columns = ['name', 'country', 'description', 'is_active']

    can_create = True
    can_edit = True
    can_delete = True

    edit_template = 'admin/market_sweep_edit.html'

    def on_model_change(self, form, model, is_created):
        if is_created:
            model.uploaded_by = current_user.id

    @expose('/upload-companies/<int:sweep_id>', methods=['POST'])
    def upload_companies(self, sweep_id):
        """Handle CSV/Excel upload for a sweep."""
        sweep = MarketSweep.query.get_or_404(sweep_id)

        file = request.files.get('companies_file')
        if not file:
            flash('No file selected', 'error')
            return redirect(self.get_url('.edit_view', id=sweep_id))

        try:
            rows = parse_companies_file(file, filename=file.filename)
        except ValueError as e:
            flash(str(e), 'error')
            return redirect(self.get_url('.edit_view', id=sweep_id))
        except Exception as e:
            flash(f'Error reading file: {str(e)}', 'error')
            return redirect(self.get_url('.edit_view', id=sweep_id))

        # Clear existing companies
        MarketSweepCompany.query.filter_by(sweep_id=sweep_id).delete()

        if rows:
            sample_keys = list(rows[0].keys())
            flash(f'Detected columns: {sample_keys}', 'info')

        count = 0
        for idx, row in enumerate(rows):
            name = str(row.get('company_name') or '').strip()
            if not name:
                continue
            company = MarketSweepCompany(
                sweep_id=sweep_id,
                company_name=name,
                ticker=str(row.get('ticker') or '').strip() or None,
                sector_label=str(row.get('sector') or '').strip() or None,
                market_cap=str(row.get('market_cap') or '').strip() or None,
                exchange=str(row.get('exchange') or '').strip() or None,
                sort_order=idx,
            )
            db.session.add(company)
            count += 1

        sweep.total_companies = count
        db.session.commit()

        flash(f'Uploaded {count} companies to "{sweep.name}"', 'success')
        return redirect(self.get_url('.edit_view', id=sweep_id))


def _sync_admin_emails(app):
    """Promote/demote users based on ADMIN_EMAILS env var (comma-separated)."""
    raw = os.environ.get('ADMIN_EMAILS', '')
    if not raw:
        return
    admin_emails = {e.strip().lower() for e in raw.split(',') if e.strip()}
    with app.app_context():
        try:
            changed = False
            for user in User.query.all():
                should_be_admin = user.email.lower() in admin_emails
                if user.is_admin != should_be_admin:
                    user.is_admin = should_be_admin
                    changed = True
                    app.logger.info(f"Admin {'granted' if should_be_admin else 'revoked'}: {user.email}")
            if changed:
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.warning(f"Could not sync admin emails (pending migration?): {e}")


def init_admin(app):
    """
    Initialize Flask-Admin with the app.

    Call this from create_app() or app/__init__.py
    """
    _sync_admin_emails(app)

    admin = Admin(
        app,
        name=f"{app.config['APP_NAME']} Admin",
        index_view=SecureAdminIndexView(),
    )

    # Add model views
    admin.add_view(SystemConfigView(SystemConfig, db.session, name='System Config', category='Configuration'))
    admin.add_view(InvestorProfileView(InvestorProfile, db.session, name='Investor Profiles', category='Configuration'))

    admin.add_view(PromptVersionView(PromptVersion, db.session, name='Prompt Versions', category='AI Prompts'))
    admin.add_view(PromptUsageLogView(PromptUsageLog, db.session, name='Usage Analytics', category='AI Prompts'))
    admin.add_view(AIResearchFeedbackView(AIResearchFeedback, db.session, name='AI Research Feedback', category='AI Prompts'))

    # User Management & Token Monitoring
    admin.add_view(UserView(User, db.session, name='Users & Tokens', category='User Management'))

    # Market Sweep
    admin.add_view(MarketSweepAdminView(MarketSweep, db.session, name='Market Sweeps', category='Market Sweep'))

    return admin
