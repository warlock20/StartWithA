from flask import Blueprint

journal_bp = Blueprint('journal', 
                       __name__, 
                       template_folder='templates', 
                       url_prefix='/company/<int:company_id>/journal')

from app.journal import routes