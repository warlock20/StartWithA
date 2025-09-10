from flask import Blueprint

ideas_bp = Blueprint('ideas', __name__, 
                     template_folder='templates', 
                     url_prefix='/ideas')

from app.ideas import routes