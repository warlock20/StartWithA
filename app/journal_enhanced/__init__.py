from flask import Blueprint

journal_enhanced_bp = Blueprint('journal_enhanced', __name__, 
                               template_folder='templates', 
                               url_prefix='/journal')

from app.journal_enhanced import routes