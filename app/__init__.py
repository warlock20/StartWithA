from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager # Ensure this is imported
from config import Config
from flask_caching import Cache
from celery_app import celery

db = SQLAlchemy()

login_manager = LoginManager() # 1. login_manager instance created at module level
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

cache = Cache()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app) 
    cache.init_app(app)

    celery.conf.update(app.config)
    
    from app.auth import auth_bp 
    app.register_blueprint(auth_bp) 
    
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
    
    from app.logs import logs_bp
    app.register_blueprint(logs_bp)
    
    from app.question_bank import question_bank_bp
    app.register_blueprint(question_bank_bp)
    
    from app.sectors import sectors_bp
    app.register_blueprint(sectors_bp)
    
    from app.journal import journal_bp
    app.register_blueprint(journal_bp)
    
    from app.ideas import ideas_bp
    app.register_blueprint(ideas_bp)

    return app