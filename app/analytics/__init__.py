from flask import Blueprint

analytics_bp = Blueprint('analytics', __name__, 
                        template_folder='templates', 
                        url_prefix='/analytics')

from app.analytics import routes