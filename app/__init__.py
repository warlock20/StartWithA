from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager # Ensure this is imported
from config import Config

db = SQLAlchemy()
login_manager = LoginManager() # 1. login_manager instance created at module level
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app) # 2. login_manager initialized with the app instance

    from app.auth import auth_bp 
    app.register_blueprint(auth_bp) 
    
    from app.checklists import checklists_bp 
    app.register_blueprint(checklists_bp) 
    
    # Blueprints should be registered after extensions are initialized
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    # Models are imported. models.py will need to import 'login_manager' from this 'app' package
    from app import models 

    return app