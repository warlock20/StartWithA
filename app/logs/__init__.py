# In app/logs/__init__.py
from flask import Blueprint

logs_bp = Blueprint('logs', 
                    __name__, 
                    template_folder='templates', 
                    url_prefix='/logs')

from app.logs import routes