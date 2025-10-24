from flask import Blueprint

sectors_bp = Blueprint('sectors',
                       __name__,
                       template_folder='templates',
                       url_prefix='/sectors')

from app.sectors import routes, api_routes