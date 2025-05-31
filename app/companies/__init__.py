from flask import Blueprint

companies_bp = Blueprint('companies', 
                         __name__, 
                         template_folder='templates', 
                         url_prefix='/companies')

from app.companies import routes # Import routes after blueprint definition