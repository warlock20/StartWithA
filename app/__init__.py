# In app/__init__.py
import logging

from flask import Flask, g, session, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache

from config import Config
from celery_app import celery
from app.assets import init_assets
from app.features import user_has_feature

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
cache = Cache()
# Limiter initialized without storage - will be configured via init_app with app.config
limiter = Limiter(key_func=get_remote_address)

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    app.logger.setLevel(logging.INFO)

    # Dedicated audit logger (GDPR Art. 5(2) accountability)
    audit = logging.getLogger('audit')
    audit.setLevel(logging.INFO)
    if not audit.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - AUDIT - %(message)s'
        ))
        audit.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger('yfinance').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('peewee').setLevel(logging.WARNING)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    cache.init_app(app)

    # Initialize rate limiter with storage from config
    # Uses Redis if REDIS_URL is set, otherwise in-memory (for local dev)
    limiter.init_app(app)

    # Initialize Flask-Assets for CSS bundling
    init_assets(app)
    storage_uri = app.config.get('RATELIMIT_STORAGE_URI', 'memory://')
    app.logger.info(f"Rate limiter initialized with storage: {storage_uri.split('://')[0]}")

    # Configure Celery with Flask app config
    celery.conf.update(
        broker_url=app.config['CELERY_BROKER_URL'],
        result_backend=app.config['CELERY_RESULT_BACKEND'],
    )

    # Initialize Flask-Admin
    from app.admin import init_admin
    init_admin(app)

    # (Blueprint registrations remain the same)
    from app.auth import auth_bp
    app.register_blueprint(auth_bp)

    # Initialize Auth0 AFTER blueprint is registered
    from app.auth.auth0_routes import init_auth0
    init_auth0(app) 
    from app.checklists import checklists_bp 
    app.register_blueprint(checklists_bp) 
    from app.companies import companies_bp 
    app.register_blueprint(companies_bp)
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)
    from app.dashboard import dashboard_bp
    app.register_blueprint(dashboard_bp)
    from app.learning import learning_bp
    app.register_blueprint(learning_bp)
    from app.question_bank import question_bank_bp
    app.register_blueprint(question_bank_bp)
    from app.sectors import sectors_bp
    app.register_blueprint(sectors_bp)
    from app.ideas import ideas_bp
    app.register_blueprint(ideas_bp)
    from app.research_workflow import research_workflow_bp
    app.register_blueprint(research_workflow_bp)
    from app.analytics import analytics_bp
    app.register_blueprint(analytics_bp)
    from app.journal_enhanced import journal_enhanced_bp
    app.register_blueprint(journal_enhanced_bp)
    from app.api import api_bp
    app.register_blueprint(api_bp)
    from app.portfolio import portfolio_bp
    app.register_blueprint(portfolio_bp)
    from app.settings.profile_routes import profile_bp
    app.register_blueprint(profile_bp)

    # Add custom template filters
    @app.template_filter('nl2br')
    def nl2br_filter(text):
        """Convert newlines to HTML line breaks"""
        if text is None:
            return ''
        return text.replace('\n', '<br>\n')

    @app.template_filter('markdown')
    def markdown_filter(text):
        """Convert markdown-like formatting to HTML"""
        if text is None:
            return ''

        # Convert markdown bold (**text**) to HTML bold
        import re
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)

        # Convert newlines to HTML line breaks
        text = text.replace('\n', '<br>\n')

        return text

    @app.template_filter('blocknote_preview')
    def blocknote_preview_filter(content, max_length=120):
        """Convert BlockNote JSON content to preview text"""
        from app.utils.blocknote_utils import blocknote_preview
        return blocknote_preview(content, max_length)

    @app.template_filter('blocknote_to_html')
    def blocknote_to_html_filter(content):
        """Convert BlockNote JSON content to HTML"""
        from app.utils.blocknote_utils import blocknote_to_html
        return blocknote_to_html(content)

    # This makes the get_review_queue function available in all templates.
    from app.journal_enhanced.utils import get_review_queue
    from app.utils.quotes import get_session_quote

    @app.context_processor
    def inject_review_queue():
        # The key in the returned dictionary is the name the template will use.
        # The value is the Python function itself.
        return dict(get_review_queue=get_review_queue)

    @app.context_processor
    def inject_investor_quote():
        """Inject the current session's investor quote into all templates"""
        quote_data = get_session_quote()

        # Check if user has dismissed the banner in this session
        show_banner = not session.get('quote_banner_dismissed', False)

        return dict(
            investor_quote=quote_data,
            show_quote_banner=show_banner
        )

    @app.context_processor
    def inject_smart_navigation():
        """Inject smart navigation URLs into all templates"""
        from app.utils.navigation_utils import get_smart_return_url
        return_url, context_label = get_smart_return_url()
        return dict(
            return_url=return_url,
            context_label=context_label
        )

    @app.context_processor
    def inject_feature_access():
        """Make has_feature() and is_newly_unlocked() available in all templates"""
        from app.features import FEATURE_TO_GROUP

        def has_feature(feature_name):
            if not current_user.is_authenticated:
                return False
            cache = getattr(g, '_feature_cache', None)
            if cache is None:
                cache = {}
                g._feature_cache = cache
            if feature_name not in cache:
                cache[feature_name] = user_has_feature(current_user, feature_name)
            return cache[feature_name]

        def is_newly_unlocked(feature_name):
            if not current_user.is_authenticated:
                return False
            newly = getattr(current_user, 'newly_unlocked_features', None) or {}
            group = FEATURE_TO_GROUP.get(feature_name)
            return group is not None and group in newly

        def get_tier_info():
            if not current_user.is_authenticated:
                return None
            tier = current_user.subscription_tier or 'free'
            if tier != 'free' or current_user.show_advanced_features:
                return None
            cache = getattr(g, '_tier_info_cache', None)
            if cache is not None:
                return cache
            from app.services.feature_unlock_service import FeatureUnlockService
            progress = FeatureUnlockService.get_unlock_progress(current_user)
            total_groups = 4
            unlocked_count = total_groups - len(progress)
            info = {
                'tier': 'free',
                'progress': progress,
                'unlocked_count': unlocked_count,
                'total_groups': total_groups,
                'remaining': len(progress),
            }
            g._tier_info_cache = info
            return info

        return dict(has_feature=has_feature, is_newly_unlocked=is_newly_unlocked, get_tier_info=get_tier_info)

    # ── Security headers ──────────────────────────────────────────────
    @app.after_request
    def set_security_headers(response):
        # HTTPS enforcement (Railway terminates TLS at the proxy)
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        # Prevent clickjacking
        response.headers['X-Frame-Options'] = 'DENY'

        # Prevent MIME-type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'

        # Referrer policy — send origin only to external sites
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Permissions policy — disable features we don't use
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'

        # Content Security Policy
        csp = "; ".join([
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' blob: https://cdn.jsdelivr.net https://unpkg.com https://cdnjs.cloudflare.com",
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com https://cdnjs.cloudflare.com https://fonts.googleapis.com",
            "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com",
            "img-src 'self' data: https:",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ])
        response.headers['Content-Security-Policy'] = csp

        return response

    # Custom error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()  # Rollback any failed database transactions
        app.logger.error(f'Server Error: {error}')
        return render_template('errors/500.html'), 500

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(429)
    def ratelimit_error(error):
        # Return JSON for API requests, HTML for browser requests
        if request.path.startswith('/api/') or request.accept_mimetypes.best == 'application/json':
            return jsonify({
                'success': False,
                'error': 'Rate limit exceeded. Please slow down.',
                'retry_after': error.description
            }), 429
        return render_template('errors/429.html'), 429

    return app