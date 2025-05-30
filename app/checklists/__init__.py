from flask import Blueprint

# Define the blueprint: 'checklists' is the name of this blueprint.
# template_folder='templates' will look for app/checklists/templates/
# url_prefix='/checklists' means all routes in this blueprint will start with /checklists
checklists_bp = Blueprint('checklists', __name__, template_folder='templates', url_prefix='/checklists')

from app.checklists import routes # Import routes after blueprint definition