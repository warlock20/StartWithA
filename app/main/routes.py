from flask import redirect, url_for, flash
from flask_login import login_required 
from app.main import bp # Assuming your blueprint is 'bp'

@bp.route('/') # Assuming 'bp' is your main blueprint instance
@login_required
def index():
    return redirect(url_for('dashboard.index'))
    # return redirect(url_for('checklists.list_checklists'))
    # or
    # #return redirect(url_for('research.list_research_sessions')) 

                                                                                                 
