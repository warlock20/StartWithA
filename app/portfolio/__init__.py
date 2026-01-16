from flask import Blueprint

portfolio_bp = Blueprint('portfolio',
                         __name__,
                         template_folder='templates',
                         url_prefix='/portfolio')

from app.portfolio import (api_routes, routes, transactions,
                           portfolio_journal,checkpoint)
