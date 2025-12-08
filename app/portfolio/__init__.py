from flask import Blueprint

portfolio_bp = Blueprint('portfolio',
                         __name__,
                         template_folder='templates',
                         url_prefix='/portfolio')

from app.portfolio import routes
