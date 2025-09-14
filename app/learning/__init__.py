from flask import Blueprint

learning_bp = Blueprint('learning', __name__, 
                       template_folder='templates', 
                       url_prefix='/learning')

from app.learning import routes