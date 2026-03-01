from flask import redirect, url_for, flash, render_template, jsonify
from flask_login import login_required, current_user
from app.main import bp # Assuming your blueprint is 'bp'

@bp.route('/health')
def health_check():
    """Health check endpoint for Railway/load balancers"""
    return jsonify({"status": "healthy", "service": "investment-platform"}), 200

@bp.route('/') # 'bp' is your main blueprint instance
def index():
    # If the user is logged in, redirect them to their dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    # If the user is a visitor (not logged in), show them the new public homepage
    return render_template('main/public_home.html', title='Welcome - Research Platform')

@bp.route('/mental-models')
def mental_models():
    return render_template('main/mental_models.html', title="Mental Models")

@bp.route('/legal/imprint')
def imprint():
    return render_template('main/legal/imprint.html', title="Imprint / Impressum")

@bp.route('/legal/privacy')
def privacy():
    return render_template('main/legal/privacy.html', title="Privacy Policy")

@bp.route('/legal/terms')
def terms():
    return render_template('main/legal/terms.html', title="Terms of Use")

@bp.route('/legal/cookies')
def cookies():
    return render_template('main/legal/cookies.html', title="Cookie Policy")
                                                                                                 
