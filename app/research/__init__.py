from flask import Blueprint

research_bp = Blueprint('research', 
                        __name__, 
                        template_folder='templates', 
                        url_prefix='/research')

from app.research import routes # Import routes after blueprint definition