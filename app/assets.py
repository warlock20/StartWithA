"""Flask-Assets configuration — CSS bundling and minification.

Replaces the 85+ @import url() calls in design-system.css with a single
minified, fingerprinted bundle in production. In debug mode, individual
files are served for easy debugging.
"""
from flask_assets import Environment, Bundle

assets = Environment()

# CSS bundle: exact order mirrors design-system.css (cascade order matters)
css_all = Bundle(
    # CORE MODULES
    'css/modules/_variables.css',
    'css/modules/_base.css',

    # COMPONENT MODULES
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

    # UTILITY & HELPER MODULES
    'css/modules/_utilities.css',
    'css/modules/_sort-controls.css',
    'css/modules/_drag-and-drop.css',

    # PAGE-SPECIFIC MODULES
    'css/modules/_auth.css',
    'css/modules/_public-home.css',
    'css/modules/_idea-capture.css',
    'css/modules/_idea-promote.css',
    'css/modules/_action-page.css',
    'css/modules/_dashboard.css',
    'css/modules/_pipeline-flow.css',
    'css/modules/_idea-pipeline.css',
    'css/modules/_sector-analysis.css',
    'css/modules/_sector-research.css',
    'css/modules/_research-sources.css',
    'css/modules/_research-checklist.css',
    'css/modules/_ai-research-assistant.css',
    'css/modules/_research-tabs.css',
    'css/modules/_atomic-canvas.css',
    'css/modules/_research-workspace.css',
    'css/modules/_focus-mode.css',
    'css/modules/_page-selector.css',
    'css/modules/_floating-quick-tools.css',
    'css/modules/_company-tags.css',
    'css/modules/_generate-document.css',
    'css/modules/_research-projects.css',
    'css/modules/_destination-analysis.css',
    'css/modules/_checkpoint-edit.css',
    'css/modules/_investment-journey.css',
    'css/modules/_thesis-update.css',
    'css/modules/_companies-list.css',
    'css/modules/_project-dashboard.css',
    'css/modules/_project-summary.css',
    'css/modules/_create-template.css',
    'css/modules/_start-research.css',
    'css/modules/_kill-room.css',
    'css/modules/_checklist-view.css',
    'css/modules/_analytics-hub.css',
    'css/modules/_journal-home.css',
    'css/modules/_journal-search.css',
    'css/modules/_learning-dashboard.css',
    'css/modules/_learning-paths.css',
    'css/modules/_learning-mistakes.css',
    'css/modules/_knowledge-library.css',
    'css/modules/_knowledge-hub.css',
    'css/modules/_learning-weekly-review.css',
    'css/modules/_mental-models.css',
    'css/modules/_mark-too-hard.css',
    'css/modules/_company-dashboard.css',
    'css/modules/_portfolio.css',
    'css/modules/_portfolio-analytics.css',
    'css/modules/_position-detail.css',
    'css/modules/_recommendations.css',

    # Standalone page CSS (previously @import url in design-system.css)
    'css/learning-insights.css',
    'css/intelligence-hub.css',
    'css/thesis-reality.css',
    'css/checkpoints.css',

    # Remaining modules
    'css/modules/_coc-analytics.css',
    'css/modules/_profile.css',
    'css/modules/_investment-profile.css',
    'css/modules/_hashtag-autocomplete.css',
    'css/modules/_warnings-widget.css',
    'css/modules/_free-research.css',
    'css/modules/_checklist-verification.css',
    'css/modules/_research-command-center.css',
    'css/modules/_idea-inbox.css',
    'css/modules/_research-focus.css',
    'css/modules/_companion.css',
    'css/modules/_cookie-notice.css',
    'css/modules/_market-sweep.css',
    'css/modules/_page-loading.css',

    filters='rcssmin',
    output='css/gen/design-system.%(version)s.css',
)


def init_assets(app):
    """Initialize Flask-Assets with the app."""
    # Configure via Flask config keys (Flask-Assets reads these automatically)
    app.config['ASSETS_DEBUG'] = app.debug
    app.config['ASSETS_AUTO_BUILD'] = app.debug

    assets.init_app(app)
    assets.register('css_all', css_all)
