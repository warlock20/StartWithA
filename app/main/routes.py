from flask import redirect, url_for, flash, render_template
from flask_login import login_required, current_user
from app.main import bp # Assuming your blueprint is 'bp'

@bp.route('/') # 'bp' is your main blueprint instance
def index():
    # If the user is logged in, redirect them to their dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    # If the user is a visitor (not logged in), show them the new public homepage
    return render_template('main/public_home.html', title='Welcome - Research Platform')
                                                                                                 
