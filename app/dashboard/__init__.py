# In app/dashboard/__init__.py
from flask import Blueprint

dashboard_bp = Blueprint('dashboard', 
                         __name__, 
                         template_folder='templates', 
                         url_prefix='/dashboard')

from app.dashboard import routes