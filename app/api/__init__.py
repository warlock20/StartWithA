from flask import Blueprint
from app import limiter
from app.constants import RATELIMIT_API

api_bp = Blueprint('api', __name__, url_prefix='/api')

# Apply rate limit to all API routes
limiter.limit(RATELIMIT_API)(api_bp)

from app.api import routes