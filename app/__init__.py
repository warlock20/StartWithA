# company_research_platform/app/__init__.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config

# Initialize extensions
db = SQLAlchemy()

def create_app(config_class=Config):
    """
    Factory function to create and configure the Flask application.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize Flask extensions here
    db.init_app(app)

    # Register blueprints here (we'll do this later for routes)
    # For example:
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    # Import models here to ensure they are known to SQLAlchemy
    # before database creation or operations.
    # It's common to put this at the bottom to avoid circular imports.
    from app import models

    return app