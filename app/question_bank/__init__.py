from flask import Blueprint

question_bank_bp = Blueprint('question_bank', 
                             __name__, 
                             template_folder='templates', 
                             url_prefix='/question_bank')

from app.question_bank import routes