# In app/__init__.py
from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from config import Config
from flask_caching import Cache
from celery_app import celery

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
cache = Cache()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Configure logging
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    app.logger.setLevel(logging.INFO)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    cache.init_app(app)

    celery.conf.update(app.config)

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
    from app.research import research_bp 
    app.register_blueprint(research_bp)
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

    # Custom error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        from flask import render_template
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        from flask import render_template
        db.session.rollback()  # Rollback any failed database transactions
        app.logger.error(f'Server Error: {error}')
        return render_template('errors/500.html'), 500

    @app.errorhandler(403)
    def forbidden_error(error):
        from flask import render_template
        return render_template('errors/403.html'), 403

    return app