"""
Admin Dashboard

Flask-Admin based admin interface for managing:
- System configuration
- Investor profiles
- Prompt versions
- Analytics
"""

from flask import Blueprint
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_login import current_user
from flask import redirect, url_for, request

from app import db
from app.models import (
    SystemConfig,
    InvestorProfile,
    UserInvestmentProfile,
    PromptVersion,
    PromptUsageLog,
    User,
)


class SecureModelView(ModelView):
    """
    Base ModelView that requires admin authentication.
    """
    def is_accessible(self):
        # TODO: Add proper admin role check
        # For now, just check if user is authenticated
        return current_user.is_authenticated

    def inaccessible_callback(self, name, **kwargs):
        # Redirect to login page if not authenticated
        return redirect(url_for('auth.login', next=request.url))


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


def init_admin(app):
    """
    Initialize Flask-Admin with the app.

    Call this from create_app() or app/__init__.py
    """
    admin = Admin(
        app,
        name='Investment Platform Admin'
    )

    # Add model views
    admin.add_view(SystemConfigView(SystemConfig, db.session, name='System Config', category='Configuration'))
    admin.add_view(InvestorProfileView(InvestorProfile, db.session, name='Investor Profiles', category='Configuration'))

    admin.add_view(PromptVersionView(PromptVersion, db.session, name='Prompt Versions', category='AI Prompts'))
    admin.add_view(PromptUsageLogView(PromptUsageLog, db.session, name='Usage Analytics', category='AI Prompts'))

    return admin
