from flask import Blueprint

research_workflow_bp = Blueprint('research_workflow', __name__, 
                                 template_folder='templates', 
                                 url_prefix='/research/workflow')

from app.research_workflow import routes