from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, current_user, logout_user, login_required
from app import db
from app.models import User
from app.auth import auth_bp # Import the blueprint from this package's __init__.py


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')

        # Basic Validation
        if not username or not email or not password or not password_confirm:
            flash('All fields are required.', 'error')
            return render_template('register.html', title="Register")

        if password != password_confirm:
            flash('Passwords do not match.', 'error')
            return render_template('register.html', title="Register", username=username, email=email)

        # Check if username or email already exists
        existing_user_by_username = User.query.filter_by(username=username).first()
        if existing_user_by_username:
            flash('That username is already taken. Please choose a different one.', 'error')
            return render_template('register.html', title="Register", email=email) # Keep email if username fails

        existing_user_by_email = User.query.filter_by(email=email).first()
        if existing_user_by_email:
            flash('That email address is already registered. Please use a different one or login.', 'error')
            return render_template('register.html', title="Register", username=username) # Keep username if email fails
        
        # If all checks pass, create new user
        new_user = User(username=username, email=email,subscription_tier=current_app.config['DEFAULT_USER_TIER'])
        new_user.set_password(password) # Hash the password
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login')) # Redirect to login page (we'll create this next)
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred during registration: {str(e)}', 'error')
            return render_template('register.html', title="Register", username=username, email=email)

    # For GET request, just display the form
    return render_template('register.html', title="Register")

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: # If user is already logged in, redirect them
        flash('You are already logged in.', 'info')
        return redirect(url_for('research.list_research_sessions')) # Or a dashboard page

    if request.method == 'POST':
        identifier = request.form.get('identifier') # Can be username or email
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False # Check for "remember me"

        if not identifier or not password:
            flash('Both username/email and password are required.', 'error')
            return render_template('login.html', title="Login")

        # Try to find user by username or email
        user_by_username = User.query.filter_by(username=identifier).first()
        user_by_email = User.query.filter_by(email=identifier).first()

        user = user_by_username or user_by_email

        if user and user.check_password(password):
            login_user(user, remember=remember) # Log in the user with Flask-Login
            flash('Login successful!', 'success')

            # Redirect to the page the user was trying to access, or a default page
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            else:
                # Redirect to a sensible default page after login
                return redirect(url_for('research.list_research_sessions')) 
        else:
            flash('Invalid username/email or password. Please try again.', 'error')
            return render_template('login.html', title="Login", identifier=identifier)

    # For GET request
    return render_template('login.html', title="Login")

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user() # Flask-Login function to clear the user session
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login')) # Redirect to login page after logout
