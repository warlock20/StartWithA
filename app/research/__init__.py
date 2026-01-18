from flask import Blueprint

research_bp = Blueprint('research',
                        __name__,
                        template_folder='templates',
                        url_prefix='/research')

from app.research import routes  # Import routes after blueprint definition
from app.research import ai_research_assistant_routes  # Import AI assistant routes