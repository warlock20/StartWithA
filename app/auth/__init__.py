from flask import Blueprint

# Define the blueprint: 'auth' is the name of this blueprint.
# __name__ helps Flask locate the blueprint.
# template_folder='templates' tells this blueprint to look for its templates
# in a subfolder named 'templates' WITHIN the blueprint's directory (i.e., app/auth/templates/)
# We'll use a URL prefix to avoid route name collisions and organize URLs.
auth_bp = Blueprint('auth', __name__, template_folder='templates', url_prefix='/auth')

from app.auth import routes  # Import routes after blueprint definition to avoid circular imports
from app.auth import auth0_routes  # Import Auth0 routes to register them with the blueprint