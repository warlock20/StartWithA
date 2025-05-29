from flask import render_template, request, redirect, url_for, flash, current_app, send_from_directory
from flask_login import current_user, login_required
from app import db
from app.models import User, Checklist, ChecklistItem, Company, ResearchSession, ResearchAnswer, CompanyDocument # <--- Ensure CompanyDocument is here
from app.main import bp # Assuming your blueprint is 'bp'

# Utility imports needed for document handling
import os
import uuid
from werkzeug.utils import secure_filename
from datetime import datetime 


@bp.route('/register', methods=['GET', 'POST'])
def register():
    # If we implement Flask-Login fully, we might want to redirect if user is already logged in
    # if current_user.is_authenticated:
    #     return redirect(url_for('main.list_checklists')) # Or a dashboard page

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')

        # Basic Validation
        if not username or not email or not password or not password_confirm:
            flash('All fields are required.', 'error')
            return render_template('main/register.html', title="Register")

        if password != password_confirm:
            flash('Passwords do not match.', 'error')
            return render_template('main/register.html', title="Register", username=username, email=email)

        # Check if username or email already exists
        existing_user_by_username = User.query.filter_by(username=username).first()
        if existing_user_by_username:
            flash('That username is already taken. Please choose a different one.', 'error')
            return render_template('main/register.html', title="Register", email=email) # Keep email if username fails

        existing_user_by_email = User.query.filter_by(email=email).first()
        if existing_user_by_email:
            flash('That email address is already registered. Please use a different one or login.', 'error')
            return render_template('main/register.html', title="Register", username=username) # Keep username if email fails
        
        # If all checks pass, create new user
        new_user = User(username=username, email=email)
        new_user.set_password(password) # Hash the password
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('main.login')) # Redirect to login page (we'll create this next)
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred during registration: {str(e)}', 'error')
            return render_template('main/register.html', title="Register", username=username, email=email)

    # For GET request, just display the form
    return render_template('main/register.html', title="Register")

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: # If user is already logged in, redirect them
        flash('You are already logged in.', 'info')
        return redirect(url_for('main.list_research_sessions')) # Or a dashboard page

    if request.method == 'POST':
        identifier = request.form.get('identifier') # Can be username or email
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False # Check for "remember me"

        if not identifier or not password:
            flash('Both username/email and password are required.', 'error')
            return render_template('main/login.html', title="Login")

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
                return redirect(url_for('main.list_research_sessions')) 
        else:
            flash('Invalid username/email or password. Please try again.', 'error')
            return render_template('main/login.html', title="Login", identifier=identifier)

    # For GET request
    return render_template('main/login.html', title="Login")

@bp.route('/logout')
@login_required
def logout():
    logout_user() # Flask-Login function to clear the user session
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.login')) # Redirect to login page after logout

@bp.route('/')
@bp.route('/checklists', methods=['GET'])
@login_required 
def list_checklists():
    # Show checklists for the currently logged-in user
    checklists = Checklist.query.filter_by(user_id=current_user.id).order_by(Checklist.name).all()
    return render_template('main/list_checklists.html', checklists=checklists, title=f"{current_user.username}'s Checklists")

@bp.route('/checklists/new', methods=['GET', 'POST'])
@login_required
def new_checklist():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        if not name:
            flash('Checklist name is required!', 'error') # Using flash for feedback
            return redirect(url_for('main.new_checklist'))

        new_checklist_obj = Checklist(name=name, description=description, author=current_user) 
        db.session.add(new_checklist_obj)
        
        # Add initial items (simple example, could be more dynamic with JS on frontend)
        item_texts = request.form.getlist('item_text[]') # Allows multiple items
        for i, text in enumerate(item_texts):
            if text.strip(): # Only add non-empty items
                item = ChecklistItem(text=text, checklist=new_checklist_obj, order=i)
                db.session.add(item)
        
        db.session.commit()
        flash('Checklist created successfully!', 'success')
        return redirect(url_for('main.view_checklist', checklist_id=new_checklist_obj.id))

    return render_template('main/new_checklist.html', title="New Checklist")

@bp.route('/checklists/<int:checklist_id>', methods=['GET'])
@login_required
def view_checklist(checklist_id):
    checklist = Checklist.query.get_or_404(checklist_id)
    if checklist.author != current_user: # Authorization check
        flash('You are not authorized to view this checklist.', 'error')
        return redirect(url_for('main.list_checklists'))
    top_level_items = checklist.items.filter_by(parent_id=None).order_by(ChecklistItem.order).all()
    user_companies = Company.query.filter_by(user_id=current_user.id).order_by(Company.name).all()
    
    return render_template(
        'main/view_checklist.html',
        checklist=checklist,
        items=top_level_items,
        title=checklist.name,
        ChecklistItem=ChecklistItem,
        companies=user_companies 
    )
    
@bp.route('/checklists/<int:checklist_id>/add_item', methods=['POST'])
@login_required
def add_checklist_item(checklist_id):
    checklist = Checklist.query.get_or_404(checklist_id)
    if checklist.author != current_user: # Authorization check
        flash('You are not authorized to modify this checklist.', 'error')
        return redirect(url_for('main.list_checklists')) 

    # For simplicity, assume current user owns this or is default.
    # Add proper authorization later.

    item_text = request.form.get('item_text')
    parent_id_str = request.form.get('parent_id') # For sub-items
    
    parent_id = None
    if parent_id_str and parent_id_str.isdigit():
        parent_id = int(parent_id_str)
        # Ensure parent_id belongs to this checklist
        parent_item_check = ChecklistItem.query.filter_by(id=parent_id, checklist_id=checklist.id).first()
        if not parent_item_check:
            flash('Invalid parent item selected.', 'error')
            return redirect(url_for('main.view_checklist', checklist_id=checklist_id))

    if item_text:
        # Determine order for the new item
        if parent_id:
            current_max_order = db.session.query(db.func.max(ChecklistItem.order)).filter_by(checklist_id=checklist_id, parent_id=parent_id).scalar()
        else:
            current_max_order = db.session.query(db.func.max(ChecklistItem.order)).filter_by(checklist_id=checklist_id, parent_id=None).scalar()
        
        new_order = (current_max_order or -1) + 1

        new_item = ChecklistItem(text=item_text, checklist_id=checklist.id, parent_id=parent_id, order=new_order)
        db.session.add(new_item)
        db.session.commit()
        flash('Item added successfully!', 'success')
    else:
        flash('Item text cannot be empty.', 'error')
        
    return redirect(url_for('main.view_checklist', checklist_id=checklist_id))

@bp.route('/companies', methods=['GET'])
@login_required
def list_companies():
    # Fetch only companies created by the current user
    companies = Company.query.filter_by(user_id=current_user.id).order_by(Company.name).all()
    # Or using the backref: companies = current_user.companies.order_by(Company.name).all()
    return render_template('main/list_companies.html', companies=companies, title=f"{current_user.username}'s Companies")

@bp.route('/companies/new', methods=['GET', 'POST'])
@login_required
def new_company():
    if request.method == 'POST':
        name = request.form.get('name')
        ticker_symbol = request.form.get('ticker_symbol', '').upper()

        if not name or not ticker_symbol:
            flash('Company name and ticker symbol are required.', 'error')
            return redirect(url_for('main.new_company')) # Consider re-rendering form with values

        # Check if this user already has a company with the same name or ticker
        # This implements the per-user uniqueness mentioned in model comments
        existing_company_by_name = Company.query.filter_by(name=name, user_id=current_user.id).first()
        existing_company_by_ticker = Company.query.filter_by(ticker_symbol=ticker_symbol, user_id=current_user.id).first()

        if existing_company_by_name:
            flash(f'You already have a company named "{name}".', 'error')
        elif existing_company_by_ticker:
            flash(f'You already have a company with ticker "{ticker_symbol}".', 'error')
        else:
            # Associate with current_user
            company = Company(name=name, ticker_symbol=ticker_symbol, creator=current_user) 
            # Or: company = Company(name=name, ticker_symbol=ticker_symbol, user_id=current_user.id)
            db.session.add(company)
            db.session.commit()
            flash(f'Company "{name}" ({ticker_symbol}) added successfully.', 'success')

            # Handle 'next' URL parameter if present (from select_checklist_for_company page)
            next_url = request.args.get('next')
            if next_url:
                return redirect(next_url)
            return redirect(url_for('main.list_companies'))

        # If error, re-render form (or redirect if that's simpler for now)
        # To re-render with values, you'd pass them back to the template
        return render_template('main/new_company.html', title="Add New Company", name=name, ticker_symbol=ticker_symbol)


    return render_template('main/new_company.html', title="Add New Company")

@bp.route('/company/<int:company_id>/select_checklist', methods=['GET'])
@login_required
def select_checklist_for_company(company_id):
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
    # Or if company.creator != current_user: (if using the backref)
        flash('You are not authorized to access this company.', 'error')
        return redirect(url_for('main.list_companies'))

    user_checklists = Checklist.query.filter_by(user_id=current_user.id).order_by(Checklist.name).all()
    
    if not user_checklists:
        flash("You don't have any checklists yet. Please create one first.", 'warning')
        # Pass 'next' to redirect back here after creating a checklist
        return redirect(url_for('main.new_checklist', next=url_for('main.select_checklist_for_company', company_id=company_id)))

    checklists_data = []
    for chk in user_checklists:
        existing_session = ResearchSession.query.filter_by(
            user_id=current_user.id,
            company_id=company.id,
            checklist_id=chk.id
        ).first()
        
        session_info = {
            'checklist_obj': chk, # Store the actual checklist object
            'existing_session_id': None,
            'existing_session_status': None,
            'resume_item_id': None,
            'item_count': chk.items.count() # Get item count for display
        }

        if existing_session:
            session_info['existing_session_id'] = existing_session.id
            session_info['existing_session_status'] = existing_session.status
            if existing_session.status == 'in_progress':
                # Calculate resume_item_id for in-progress sessions
                all_items = get_all_ordered_items_for_checklist(chk.id)
                if all_items:
                    resume_id_candidate = all_items[0].id # Default to first item
                    for item in all_items:
                        ans_exists = ResearchAnswer.query.filter_by(
                            research_session_id=existing_session.id, 
                            checklist_item_id=item.id
                        ).first()
                        if not ans_exists:
                            resume_id_candidate = item.id
                            break
                    session_info['resume_item_id'] = resume_id_candidate
                # If no items in checklist, resume_item_id remains None
        
        checklists_data.append(session_info)

    return render_template('main/select_checklist_for_company.html',
                           company=company,
                           checklists_data=checklists_data,
                           title=f"Select or Resume Research for {company.name}")

@bp.route('/research/start', methods=['POST'])
@login_required  # Ensures only logged-in users can access this route
def start_research_session():
    """
    Handles the initiation of a research session.
    It checks if a session for the given user, company, and checklist already exists.
    If yes:
        - Resumes an 'in_progress' session.
        - Redirects to summary for a 'completed' session.
    If no:
        - Performs authorization checks to ensure user owns the checklist and company.
        - Creates a new 'in_progress' session.
        - Redirects to the first item of the checklist for the new session.
    """

    # 1. Retrieve checklist_id and company_id from the submitted form data.
    # The 'type=int' attempts to convert the form values to integers.
    checklist_id = request.form.get('checklist_id', type=int)
    company_id = request.form.get('company_id', type=int)

    # 2. Basic validation: Ensure both IDs were actually provided by the form.
    if not checklist_id or not company_id:
        flash('Checklist and Company must be selected.', 'error')
        # Redirect to the page the user came from (request.referrer) or a default page.
        return redirect(request.referrer or url_for('main.list_checklists'))

    # 3. Uniqueness Check: Look for any existing research session matching the current user,
    #    the selected company, and the selected checklist, regardless of its status.
    existing_session = ResearchSession.query.filter_by(
        user_id=current_user.id,    # Filter by the currently logged-in user
        checklist_id=checklist_id,  # Filter by the submitted checklist_id
        company_id=company_id       # Filter by the submitted company_id
    ).first()                       # Get the first matching session, if any

    # 4. Handle the case where a session ALREADY EXISTS.
    if existing_session:
        if existing_session.status == 'in_progress':
            # 4a. If the existing session is 'in_progress', resume it.
            flash('Resuming existing in-progress research session.', 'info')
            
            # Get all items of the checklist in their defined order.
            all_items_in_order = get_all_ordered_items_for_checklist(existing_session.checklist_id)
            
            if not all_items_in_order:
                # Edge case: The checklist associated with the session has no items.
                flash('The checklist for this session has no items!', 'warning')
                return redirect(url_for('main.view_checklist', checklist_id=existing_session.checklist_id))

            # Determine the specific item to redirect to (first unanswered item).
            redirect_to_item_id = all_items_in_order[0].id  # Default to the first item.
            for item in all_items_in_order:
                answer_exists = ResearchAnswer.query.filter_by(
                    research_session_id=existing_session.id,
                    checklist_item_id=item.id
                ).first()
                if not answer_exists:
                    redirect_to_item_id = item.id  # Found the first item without an answer.
                    break
            # Redirect to the research step for the determined item.
            return redirect(url_for('main.research_step', session_id=existing_session.id, item_id=redirect_to_item_id))
        
        elif existing_session.status == 'completed':
            # 4b. If the existing session is 'completed', show its summary.
            flash('This research was already completed. Viewing summary. You can edit answers from there.', 'info')
            return redirect(url_for('main.view_research_session_summary', session_id=existing_session.id))
        
        else:
            # 4c. Handle any other unforeseen statuses for an existing session.
            flash(f'A session for this company and checklist already exists with status: {existing_session.status}. Viewing details.', 'info')
            # Defaulting to the summary page for any other existing status.
            return redirect(url_for('main.view_research_session_summary', session_id=existing_session.id))
    
    # 5. If no existing session was found (the 'if existing_session:' block was not entered),
    #    then proceed to create a NEW research session.

    # 5a. Fetch the full Checklist and Company objects from the database using their IDs.
    #     '.get_or_404()' will automatically return a 404 "Not Found" page if an ID doesn't exist.
    checklist = Checklist.query.get_or_404(checklist_id)
    company = Company.query.get_or_404(company_id)

    # 5b. Authorization Checks: Verify that the current user owns the selected checklist and company.
    #     This is critical for data privacy and integrity in a multi-user application.
    if checklist.user_id != current_user.id:
        # (Alternatively, if using backrefs: checklist.author != current_user)
        flash('You are not authorized to use this checklist.', 'error')
        return redirect(url_for('main.list_checklists'))  # Redirect to a safe page
    
    if company.user_id != current_user.id:
        # (Alternatively, if using backrefs: company.creator != current_user)
        flash('You are not authorized to research this company.', 'error')
        return redirect(url_for('main.list_companies'))  # Redirect to a safe page
    
    # 5c. If all checks pass (no existing session, user is authorized), create the new ResearchSession.
    new_session = ResearchSession(
        user_id=current_user.id,      # Link to the currently logged-in user
        checklist_id=checklist.id,    # Link to the validated checklist
        company_id=company.id,        # Link to the validated company
        status='in_progress'          # New sessions always start as 'in_progress'
    )
    try:
        db.session.add(new_session)
        db.session.commit()
        flash('New research session started!', 'success')
    except Exception as e:
        db.session.rollback() # Rollback in case of database error during commit
        flash(f'Error starting new research session: {str(e)}', 'error')
        return redirect(request.referrer or url_for('main.list_checklists'))


    # 5d. Redirect the user to the first item of the newly created research session.
    all_items_for_new_session = get_all_ordered_items_for_checklist(checklist.id)
    
    if all_items_for_new_session:
        # If the checklist has items, get the ID of the first one.
        first_item_in_new_session = all_items_for_new_session[0]
        return redirect(url_for('main.research_step', session_id=new_session.id, item_id=first_item_in_new_session.id))
    else:
        # If the checklist is empty, inform the user.
        # The session record has been created but will be un-actionable through the research_step.
        # Future improvement: Prevent session creation or delete the empty session.
        flash('This checklist has no items to research!', 'warning')
        return redirect(url_for('main.view_checklist', checklist_id=checklist_id))
    
def _get_ordered_checklist_items_recursive(parent_item_id, checklist_id):
    """
    Recursive helper to fetch items and their children in order.
    """
    ordered_items = []
    if parent_item_id is None: # Top-level items
        items = ChecklistItem.query.filter_by(checklist_id=checklist_id, parent_id=None).order_by(ChecklistItem.order).all()
    else: # Sub-items
        items = ChecklistItem.query.filter_by(checklist_id=checklist_id, parent_id=parent_item_id).order_by(ChecklistItem.order).all()

    for item in items:
        ordered_items.append(item)
        ordered_items.extend(_get_ordered_checklist_items_recursive(item.id, checklist_id))
    return ordered_items

def get_all_ordered_items_for_checklist(checklist_id):
    """
    Returns a flat list of all checklist items for a given checklist_id,
    ordered by their sequence and hierarchy (depth-first).
    """
    return _get_ordered_checklist_items_recursive(None, checklist_id)

@bp.route('/research_session/<int:session_id>/item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def research_step(session_id, item_id):
    session = ResearchSession.query.get_or_404(session_id)
    current_item = ChecklistItem.query.get_or_404(item_id)
    if session.researcher != current_user: # Authorization check (assuming 'researcher' backref)
        flash('You are not authorized to access this research session.', 'error')
        return redirect(url_for('main.list_research_sessions'))

    # Basic security check: ensure the item belongs to the session's checklist
    if current_item.checklist_id != session.checklist_id:
        flash('Invalid item for this research session.', 'error')
        return redirect(url_for('main.list_checklists')) # Or a more appropriate error page

    # Get the full ordered list of items for this session's checklist
    all_items_in_order = get_all_ordered_items_for_checklist(session.checklist_id)
    if not all_items_in_order:
        flash('Checklist has no items.', 'error')
        return redirect(url_for('main.view_checklist', checklist_id=session.checklist_id))

    current_item_index = -1
    for index, item_obj in enumerate(all_items_in_order):
        if item_obj.id == current_item.id:
            current_item_index = index
            break
    
    if current_item_index == -1: # Should not happen if item_id is valid and from this checklist
        flash('Error finding current item in checklist order.', 'error')
        return redirect(url_for('main.view_checklist', checklist_id=session.checklist_id))

    # Fetch existing answer for this item in this session
    research_answer = ResearchAnswer.query.filter_by(
        research_session_id=session.id,
        checklist_item_id=current_item.id
    ).first()

    if request.method == 'POST':
        answer_text = request.form.get('answer_text')
        if research_answer:
            research_answer.answer_text = answer_text
            research_answer.answered_at = datetime.utcnow()
        else:
            research_answer = ResearchAnswer(
                answer_text=answer_text,
                research_session_id=session.id,
                checklist_item_id=current_item.id
            )
            db.session.add(research_answer)
        db.session.commit()
        flash('Answer saved.', 'success')

        # Determine next item
        if current_item_index + 1 < len(all_items_in_order):
            next_item = all_items_in_order[current_item_index + 1]
            return redirect(url_for('main.research_step', session_id=session.id, item_id=next_item.id))
        else:
            # This is the last item
            session.status = 'completed' # Mark session as completed
            db.session.commit()
            flash('Checklist completed! Research session finished.', 'success')
            # Redirect to a summary page or back to the checklist view for now
            return redirect(url_for('main.view_research_session_summary', session_id=session.id)) # We'll create this route next

    # For GET request or if POST needs to re-render
    # progress_percent = ( (current_item_index +1) / len(all_items_in_order) ) * 100 if all_items_in_order else 0
    progress_percent = (current_item_index) / len(all_items_in_order) * 100 if all_items_in_order else 0
    
    previous_item_id = None
    if current_item_index > 0 and all_items_in_order: # Check if not the first item
        previous_item_id = all_items_in_order[current_item_index - 1].id
    ##or
    #TODO: Handle the case where the session is not calculated correctly for the last question
    # total_items_count = len(all_items_in_order)
    # answered_count = 0
    # if total_items_count > 0:
    #     # Efficiently count answers for this session
    #     answered_count = ResearchAnswer.query.filter_by(research_session_id=session.id).count()
    # progress_percent = (answered_count / total_items_count) * 100 if total_items_count > 0 else 0

    return render_template(
        'main/research_step.html',
        title=f"Research: {session.company.ticker_symbol} - Item {current_item_index + 1}/{len(all_items_in_order)}",
        session=session,
        current_item=current_item,
        answer=research_answer,
        current_item_number=current_item_index + 1,
        total_items=len(all_items_in_order),
        progress_percent=progress_percent,
        previous_item_id=previous_item_id 
    )

# We also need a route for the session summary. Let's add a placeholder for now.
@bp.route('/research_session/<int:session_id>/summary', methods=['GET'])
@login_required
def view_research_session_summary(session_id):
    session = ResearchSession.query.get_or_404(session_id)
    if session.researcher != current_user: # Authorization check
        flash('You are not authorized to view this summary.', 'error')
        return redirect(url_for('main.list_research_sessions'))
    
    # Get all items for the checklist in their correct order
    all_ordered_items = get_all_ordered_items_for_checklist(session.checklist_id)
    
    # Fetch all answers for this session and put them in a dictionary for easy lookup
    answers_query = ResearchAnswer.query.filter_by(research_session_id=session.id).all()
    answers_dict = {ans.checklist_item_id: ans.answer_text for ans in answers_query}
    
    # For completion time: find the latest 'answered_at' timestamp among answers
    # (This is a bit simplified, as the session.status is 'completed' already)
    # The template logic for last_answered_at.value is one way, or can be done here.

    return render_template(
        'main/session_summary.html', 
        title="Research Summary", 
        session=session, 
        all_ordered_items=all_ordered_items, # Pass ordered items
        answers_dict=answers_dict            # Pass answers dictionary
        # The old 'answers' variable (a list of ResearchAnswer objects) can be removed if not used
    )

@bp.route('/research_session/<int:session_id>/delete', methods=['POST'])
@login_required  
def delete_research_session(session_id):
    session_to_delete = ResearchSession.query.get_or_404(session_id)
    
    # Verify that the session belongs to the current user
    if session_to_delete.user_id != current_user.id: # Use current_user.id
        flash('You do not have permission to delete this session.', 'error')
        return redirect(url_for('main.list_research_sessions'))

    try:
        # SQLAlchemy will handle deleting associated ResearchAnswer records
        # due to cascade="all, delete-orphan" on ResearchSession.answers relationship
        db.session.delete(session_to_delete)
        db.session.commit()
        flash('Research session deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback() # Rollback in case of error
        flash(f'Error deleting research session: {str(e)}', 'error')

    return redirect(url_for('main.list_research_sessions'))
    
@bp.route('/my_research_sessions', methods=['GET'])
@login_required
def list_research_sessions():
    # Fetch all sessions for this user, ordered by start date descending
    sessions_query = ResearchSession.query.filter_by(user_id=current_user.id).order_by(ResearchSession.start_date.desc()).all()
    
    sessions_data = []
    for session in sessions_query:
        data = {
            'session_obj': session,
            'company_name': session.company.name, # Assuming session.company relationship works
            'checklist_name': session.checklist.name, # Assuming session.checklist relationship works
            'resume_item_id': None
        }
        
        if session.status == 'in_progress':
            all_items_in_order = get_all_ordered_items_for_checklist(session.checklist_id)
            if all_items_in_order:
                # Default to the first item if no other logic finds a better place
                resume_item_id_candidate = all_items_in_order[0].id 
                for item in all_items_in_order:
                    answer_exists = ResearchAnswer.query.filter_by(
                        research_session_id=session.id,
                        checklist_item_id=item.id
                    ).first()
                    if not answer_exists:
                        resume_item_id_candidate = item.id # Found the first unanswered item
                        break
                data['resume_item_id'] = resume_item_id_candidate
            else: # Checklist has no items, but session is in_progress
                data['resume_item_id'] = None # Cannot resume if no items
                
        sessions_data.append(data)

    return render_template('main/list_research_sessions.html', 
                           sessions_data=sessions_data, 
                           title="My Research Sessions")
    
@bp.route('/company/<int:company_id>/documents', methods=['GET', 'POST'])
@login_required
def manage_company_documents(company_id):
    company = Company.query.get_or_404(company_id)
    # Authorization: Ensure current user owns the company they are adding docs for
    if company.user_id != current_user.id:
        flash("You are not authorized to manage documents for this company.", "error")
        return redirect(url_for('main.list_companies'))

    if request.method == 'POST': # Handles new document upload
        if 'document_file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)

        file = request.files['document_file']
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)

        doc_group = request.form.get('document_group')
        doc_title = request.form.get('document_title')
        doc_date_str = request.form.get('document_date') # Expects YYYY-MM-DD
        doc_description = request.form.get('description')

        if not doc_group or not doc_title:
            flash('Document group and title are required.', 'error')
        elif file: # and file.filename.lower().endswith(tuple(current_app.config['ALLOWED_EXTENSIONS']))
            # (Add extension check using ALLOWED_EXTENSIONS from config)
            original_fn = secure_filename(file.filename)

            # Create a unique stored filename (e.g., using UUID + original extension)
            import uuid
            file_ext = os.path.splitext(original_fn)[1]
            stored_fn = f"{uuid.uuid4().hex}{file_ext}"

            # Define company-specific upload path
            company_specific_upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], str(company.id))
            os.makedirs(company_specific_upload_path, exist_ok=True) # Create if not exists

            file_save_path = os.path.join(company_specific_upload_path, stored_fn)
            file.save(file_save_path)

            document_date_obj = None
            if doc_date_str:
                try:
                    document_date_obj = datetime.strptime(doc_date_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Invalid date format. Please use YYYY-MM-DD.', 'error')
                    # Fall through to re-render form, or handle error more gracefully

            if not (current_app.config['ALLOWED_EXTENSIONS'] and \
                original_fn.lower().split('.')[-1] not in current_app.config['ALLOWED_EXTENSIONS']):

                new_doc = CompanyDocument(
                    company_id=company.id,
                    user_id=current_user.id, # Uploader
                    original_filename=original_fn,
                    stored_filename=os.path.join(str(company.id), stored_fn), # Path relative to UPLOAD_FOLDER base
                    document_group=doc_group,
                    document_title=doc_title,
                    document_date=document_date_obj,
                    description=doc_description
                )
                db.session.add(new_doc)
                db.session.commit()
                flash(f'Document "{original_fn}" uploaded successfully to group "{doc_group}".', 'success')
            else:
                flash('File type not allowed.', 'error')
                # os.remove(file_save_path) # Clean up saved file if type not allowed
            return redirect(url_for('main.manage_company_documents', company_id=company.id))

    # GET request: List existing documents, grouped
    # documents_query = company.documents.filter_by(user_id=current_user.id).order_by(...) # If docs are user-specific uploads
    documents_query = company.documents.order_by(CompanyDocument.document_group, CompanyDocument.document_date.desc(), CompanyDocument.document_title).all()

    grouped_documents = {}
    for doc in documents_query:
        group = doc.document_group
        if group not in grouped_documents:
            grouped_documents[group] = []
        grouped_documents[group].append(doc)

    return render_template('main/company_documents.html', 
                           company=company, 
                           grouped_documents=grouped_documents,
                           title=f"Documents for {company.name}")

# Route to serve uploaded files (we'll need this to view/download them)
@bp.route('/uploads/company_documents/<path:filepath>')
@login_required
def serve_company_document(filepath):
    # filepath will be like "<company_id>/<stored_filename>"
    # Ensure user has permission to access this company's documents.
    # Split filepath to get company_id and then check ownership.
    try:
        company_id_str = filepath.split(os.sep, 1)[0]
        company_id = int(company_id_str)
        company_check = Company.query.get_or_404(company_id)
        if company_check.user_id != current_user.id:
            flash("Not authorized to access this file.", "error")
            return redirect(url_for('main.list_companies')) # Or abort(403)
    except (ValueError, IndexError):
        # abort(404) # Invalid path format
        flash("Invalid file path format.", "error")
        return redirect(url_for('main.list_companies'))


    # Make sure UPLOAD_FOLDER is correctly joined with the relative filepath
    # The 'filepath' stored in DB is like 'company_id/stored_filename.pdf'
    # So, the actual path is base_upload_folder/filepath
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filepath, as_attachment=False) # as_attachment=True for download
                                                                                                # as_attachment=False to display in browser if possible (PDFs)   