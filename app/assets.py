"""Flask-Assets configuration — CSS bundling and minification.

Splits CSS into 4 bundles for performance:
  - css_core: Always loaded (layout, nav, shared components)
  - css_companies: Company detail, research, sectors, ideas pages
  - css_portfolio: Portfolio, analytics, dashboard pages
  - css_learning: Journal, learning center pages

In debug mode, individual files are served for easy debugging.
In production, each bundle is minified and fingerprinted.
"""
from flask_assets import Environment, Bundle

assets = Environment()

# ─── CORE BUNDLE ───────────────────────────────────────────���─────────────────
# Always loaded on every page. Layout, navigation, shared components, utilities.
css_core = Bundle(
    # Foundation
    'css/modules/_variables.css',
    'css/modules/_base.css',

    # Shared components
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

    # Utilities & helpers
    'css/modules/_utilities.css',
    'css/modules/_sort-controls.css',
    'css/modules/_drag-and-drop.css',

    # Global pages & small modules
    'css/modules/_auth.css',
    'css/modules/_public-home.css',
    'css/modules/_cookie-notice.css',
    'css/modules/_page-loading.css',
    'css/modules/_toast.css',
    'css/modules/_profile.css',
    'css/modules/_action-page.css',
    'css/modules/_floating-quick-tools.css',

    filters='rcssmin',
    output='css/gen/core.%(version)s.css',
)

# ─── COMPANIES BUNDLE ──────────────────────────────��─────────────────────────
# Company detail, research workflow, sectors, ideas pages.
css_companies = Bundle(
    'css/modules/_company-dashboard.css',
    'css/modules/_company-tags.css',
    'css/modules/_companies-list.css',
    'css/modules/_investment-journey.css',
    'css/modules/_thesis-update.css',
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
    'css/modules/_research-command-center.css',
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
    'css/modules/_pipeline-flow.css',
    'css/modules/_market-sweep.css',
    'css/modules/_intelligence-panel.css',
    'css/modules/_hashtag-autocomplete.css',
    'css/modules/_warnings-widget.css',
    'css/modules/_recommendations.css',
    'css/modules/_investment-profile.css',

    filters='rcssmin',
    output='css/gen/companies.%(version)s.css',
)

# ─── PORTFOLIO BUNDLE ───────────────────────────────────────────────��────────
# Portfolio management, analytics dashboard, position detail.
css_portfolio = Bundle(
    'css/modules/_dashboard.css',
    'css/modules/_portfolio.css',
    'css/modules/_portfolio-analytics.css',
    'css/modules/_position-detail.css',
    'css/modules/_analytics-hub.css',
    'css/modules/_coc-analytics.css',
    'css/modules/_project-dashboard.css',
    'css/modules/_project-summary.css',

    # Standalone page CSS
    'css/intelligence-hub.css',
    'css/thesis-reality.css',
    'css/checkpoints.css',

    filters='rcssmin',
    output='css/gen/portfolio.%(version)s.css',
)

# ─── LEARNING BUNDLE ─────────────────────────────────────────────────────────
# Journal entries, learning center, knowledge hub.
css_learning = Bundle(
    'css/modules/_journal-home.css',
    'css/modules/_journal-search.css',
    'css/modules/_knowledge-hub.css',
    'css/modules/_knowledge-library.css',
    'css/modules/_learning-dashboard.css',
    'css/modules/_learning-paths.css',
    'css/modules/_learning-mistakes.css',
    'css/modules/_learning-weekly-review.css',
    'css/modules/_mental-models.css',

    # Standalone page CSS
    'css/learning-insights.css',

    filters='rcssmin',
    output='css/gen/learning.%(version)s.css',
)


def init_assets(app):
    """Initialize Flask-Assets with the app."""
    app.config['ASSETS_DEBUG'] = app.debug
    app.config['ASSETS_AUTO_BUILD'] = app.debug

    assets.init_app(app)
    assets.register('css_core', css_core)
    assets.register('css_companies', css_companies)
    assets.register('css_portfolio', css_portfolio)
    assets.register('css_learning', css_learning)
