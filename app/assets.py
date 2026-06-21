# Investment Checklist Platform
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

"""Flask-Assets configuration — CSS bundling and minification.

Splits CSS into 4 page-group bundles:
  css_core       – shared layout, components, utilities (every page)
  css_companies  – companies, sectors, research, ideas, checklists
  css_portfolio  – dashboard, portfolio, analytics
  css_learning   – learning, journal, knowledge hub

Each page loads core + its page bundle (2 HTTP requests vs. 1 monolithic).
"""
from flask_assets import Environment, Bundle

assets = Environment()

# ---------------------------------------------------------------------------
# CORE — loaded on every page via _base.html
# ---------------------------------------------------------------------------
css_core = Bundle(
    # Variables & base
    'css/modules/_variables.css',
    'css/modules/_base.css',

    # Component modules
    'css/modules/_buttons.css',
    'css/modules/_button-system.css',
    'css/modules/_forms.css',
    'css/modules/_form-validation.css',
    'css/modules/_tables.css',
    'css/modules/_data-table.css',
    'css/modules/_alerts.css',
    'css/modules/_cards.css',
    'css/modules/_card-system.css',
    'css/modules/_navigation.css',
    'css/modules/_sidebar.css',
    'css/modules/_quote-banner.css',

    # Utility & helper modules
    'css/modules/_utilities.css',
    'css/modules/_sort-controls.css',
    'css/modules/_drag-and-drop.css',

    # Shared page layout & metrics (used across all bundles)
    'css/modules/_page-layout.css',
    'css/modules/_metrics-buttons.css',
    'css/modules/_research-command-center.css',

    # Page-level core
    'css/modules/_auth.css',
    'css/modules/_public-home.css',
    'css/modules/_floating-quick-tools.css',
    'css/modules/_action-page.css',
    'css/modules/_profile.css',
    'css/modules/_investment-profile.css',
    'css/modules/_cookie-notice.css',
    'css/modules/_page-loading.css',
    'css/modules/_toast.css',
    'css/modules/_mental-models.css',

    filters='rcssmin',
    output='css/gen/core.%(version)s.css',
)

# ---------------------------------------------------------------------------
# COMPANIES — companies, sectors, research workflow, ideas, checklists
# ---------------------------------------------------------------------------
css_companies = Bundle(
    'css/modules/_company-dashboard.css',
    'css/modules/_company-tags.css',
    'css/modules/_investment-journey.css',
    'css/modules/_position-detail.css',
    'css/modules/_companies-list.css',
    'css/modules/_destination-analysis.css',
    'css/modules/_checkpoint-edit.css',
    'css/modules/_checklist-view.css',
    'css/modules/_checklist-verification.css',
    'css/modules/_sector-analysis.css',
    'css/modules/_sector-research.css',
    'css/modules/_research-sources.css',
    'css/modules/_research-checklist.css',
    'css/modules/_research-tabs.css',
    'css/modules/_atomic-canvas.css',
    'css/modules/_research-workspace.css',
    'css/modules/_focus-mode.css',
    'css/modules/_page-selector.css',
    'css/modules/_research-projects.css',
    'css/modules/_research-focus.css',
    'css/modules/_ai-research-assistant.css',
    'css/modules/_generate-document.css',
    'css/modules/_company-resources.css',
    'css/modules/_document-annotations.css',
    'css/modules/_send-to-sector.css',
    'css/modules/_companion.css',
    'css/modules/_create-template.css',
    'css/modules/_start-research.css',
    'css/modules/_free-research.css',
    'css/modules/_mark-too-hard.css',
    'css/modules/_kill-room.css',
    'css/modules/_idea-capture.css',
    'css/modules/_idea-promote.css',
    'css/modules/_idea-pipeline.css',
    'css/modules/_idea-inbox.css',
    'css/modules/_market-sweep.css',
    'css/modules/_recommendations.css',
    'css/modules/_project-dashboard.css',
    'css/modules/_project-summary.css',

    filters='rcssmin',
    output='css/gen/companies.%(version)s.css',
)

# ---------------------------------------------------------------------------
# PORTFOLIO — dashboard, portfolio, analytics
# ---------------------------------------------------------------------------
css_portfolio = Bundle(
    'css/modules/_pipeline-flow.css',
    'css/modules/_portfolio-dashboard.css',
    'css/modules/_portfolio-analytics.css',
    'css/modules/_position-detail.css',
    'css/modules/_analytics-hub.css',
    'css/modules/_coc-analytics.css',
    'css/modules/_investment-journey.css',
    'css/modules/_warnings-widget.css',
    'css/modules/_intelligence-panel.css',
    'css/modules/_thesis-update.css',
    'css/intelligence-hub.css',
    'css/thesis-reality.css',
    'css/checkpoints.css',
    'css/learning-insights.css',

    filters='rcssmin',
    output='css/gen/portfolio.%(version)s.css',
)

# ---------------------------------------------------------------------------
# LEARNING — learning, journal, knowledge hub
# ---------------------------------------------------------------------------
css_learning = Bundle(
    'css/modules/_journal-home.css',
    'css/modules/_journal-search.css',
    'css/modules/_learning-mistakes.css',
    'css/modules/_knowledge-library.css',
    'css/modules/_knowledge-hub.css',
    'css/modules/_hashtag-autocomplete.css',

    filters='rcssmin',
    output='css/gen/learning.%(version)s.css',
)


def init_assets(app):
    """Initialize Flask-Assets with the app."""
    app.config['ASSETS_DEBUG'] = False
    app.config['ASSETS_AUTO_BUILD'] = app.debug

    assets.init_app(app)
    assets.register('css_core', css_core)
    assets.register('css_companies', css_companies)
    assets.register('css_portfolio', css_portfolio)
    assets.register('css_learning', css_learning)
