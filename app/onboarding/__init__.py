from flask import Blueprint

onboarding_bp = Blueprint('onboarding', __name__,
                         url_prefix='/onboarding',
                         template_folder='templates')

from app.onboarding import routes