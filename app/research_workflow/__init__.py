from flask import Blueprint

research_workflow_bp = Blueprint('research_workflow', __name__,
                                 template_folder='templates',
                                 url_prefix='/research/workflow')

# Import routes to register them with the blueprint
from app.research_workflow import (api_routes, template_routes, session_routes,
                                  project_workflow_routes, project_management_routes,
                                  project_data_routes, utility_routes)