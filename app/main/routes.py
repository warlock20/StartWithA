# company_research_platform/app/main/routes.py

import datetime
from flask import render_template, request, redirect, url_for, flash # Added flash
from app import db
from app.models import User, Checklist, ChecklistItem, ResearchSession, ResearchAnswer, Company
from app.main import bp # Import the blueprint

# Helper function to get or create a default user (for now)
def get_default_user():
    user = User.query.filter_by(username='default_user').first()
    if not user:
        user = User(username='default_user')
        db.session.add(user)
        db.session.commit()
    return user

@bp.route('/')
@bp.route('/checklists', methods=['GET'])
def list_checklists():
    # For now, let's just show checklists for the default user or all checklists
    # user = get_default_user() 
    # checklists = Checklist.query.filter_by(user_id=user.id).all()
    checklists = Checklist.query.all() # Show all for simplicity initially
    return render_template('main/list_checklists.html', checklists=checklists, title="All Checklists")

@bp.route('/checklists/new', methods=['GET', 'POST'])
def new_checklist():
    user = get_default_user() # Get or create the default user

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        if not name:
            flash('Checklist name is required!', 'error') # Using flash for feedback
            return redirect(url_for('main.new_checklist'))

        new_checklist_obj = Checklist(name=name, description=description, author=user)
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
def view_checklist(checklist_id):
    checklist = Checklist.query.get_or_404(checklist_id)
    top_level_items = checklist.items.filter_by(parent_id=None).order_by(ChecklistItem.order).all()
    all_companies = Company.query.order_by(Company.name).all() # Fetch companies

    return render_template(
        'main/view_checklist.html',
        checklist=checklist,
        items=top_level_items,
        title=checklist.name,
        ChecklistItem=ChecklistItem,
        companies=all_companies  # <--- Pass companies to the template
    )
    
@bp.route('/checklists/<int:checklist_id>/add_item', methods=['POST'])
def add_checklist_item(checklist_id):
    checklist = Checklist.query.get_or_404(checklist_id)
    user = get_default_user() # Or check if checklist.author == current_user later

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
def list_companies():
    companies = Company.query.order_by(Company.name).all()
    return render_template('main/list_companies.html', companies=companies, title="Companies")

@bp.route('/companies/new', methods=['GET', 'POST'])
def new_company():
    if request.method == 'POST':
        name = request.form.get('name')
        ticker_symbol = request.form.get('ticker_symbol', '').upper()

        if not name or not ticker_symbol:
            flash('Company name and ticker symbol are required.', 'error')
            return redirect(url_for('main.new_company'))

        existing_company_by_name = Company.query.filter_by(name=name).first()
        existing_company_by_ticker = Company.query.filter_by(ticker_symbol=ticker_symbol).first()

        if existing_company_by_name:
            flash(f'A company with the name "{name}" already exists.', 'error')
        elif existing_company_by_ticker:
            flash(f'A company with the ticker "{ticker_symbol}" already exists.', 'error')
        else:
            company = Company(name=name, ticker_symbol=ticker_symbol)
            db.session.add(company)
            db.session.commit()
            flash(f'Company "{name}" ({ticker_symbol}) added successfully.', 'success')
            return redirect(url_for('main.list_companies'))
        
        # If there was an error, redirect back to the form
        return redirect(url_for('main.new_company'))

    return render_template('main/new_company.html', title="Add New Company")

@bp.route('/research/start', methods=['POST'])
def start_research_session():
    user = get_default_user() # Assuming default user for now
    checklist_id = request.form.get('checklist_id', type=int)
    company_id = request.form.get('company_id', type=int)

    if not checklist_id or not company_id:
        flash('Checklist and Company must be selected.', 'error')
        return redirect(request.referrer or url_for('main.list_checklists'))

    # Check if this exact session already exists and is in progress
    existing_session = ResearchSession.query.filter_by(
        user_id=user.id,
        checklist_id=checklist_id,
        company_id=company_id,
        status='in_progress' 
    ).first()

    if existing_session:
        flash('Resuming existing research session for this company and checklist.', 'info')
        
        all_items_in_order = get_all_ordered_items_for_checklist(existing_session.checklist_id)
        redirect_to_item_id = None

        if not all_items_in_order:
            flash('The checklist for this session has no items!', 'warning')
            # This is an edge case, but if the checklist became empty.
            return redirect(url_for('main.view_checklist', checklist_id=existing_session.checklist_id))

        # Default to the first item if no other logic finds a better place
        redirect_to_item_id = all_items_in_order[0].id 

        for item in all_items_in_order:
            answer_exists = ResearchAnswer.query.filter_by(
                research_session_id=existing_session.id,
                checklist_item_id=item.id
            ).first()
            if not answer_exists:
                redirect_to_item_id = item.id # Found the first unanswered item
                break
        
        # If all items are answered but session is still 'in_progress' (unlikely but possible)
        # the loop will complete, and redirect_to_item_id will be the ID of the last item
        # or the first item if the list was empty after all. The current logic sets it to the 
        # first item initially, and then the last item if all are answered.
        # For a better user experience, if all items have answers, we might want to send
        # them to the summary page or the last item. For now, this takes them to the first unanswered
        # or the last item if all seem answered.

        return redirect(url_for('main.research_step', session_id=existing_session.id, item_id=redirect_to_item_id))

    # Create new session if no existing 'in_progress' one is found
    checklist = Checklist.query.get_or_404(checklist_id)
    company = Company.query.get_or_404(company_id)

    session = ResearchSession(
        user_id=user.id, 
        checklist_id=checklist.id, 
        company_id=company.id,
        status='in_progress' # Explicitly set status
    )
    db.session.add(session)
    db.session.commit()
    flash('New research session started!', 'success')

    first_item = get_all_ordered_items_for_checklist(checklist.id) # Use the helper
    
    if first_item: # first_item is now a list
        return redirect(url_for('main.research_step', session_id=session.id, item_id=first_item[0].id))
    else:
        flash('This checklist has no items to research!', 'warning')
        # If a session was created but checklist has no items, maybe delete the session or mark as 'empty'?
        # For now, just redirect.
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
def research_step(session_id, item_id):
    session = ResearchSession.query.get_or_404(session_id)
    current_item = ChecklistItem.query.get_or_404(item_id)

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
    progress_percent = ( (current_item_index +1) / len(all_items_in_order) ) * 100 if all_items_in_order else 0


    return render_template(
        'main/research_step.html',
        title=f"Research: {session.company.ticker_symbol} - Item {current_item_index + 1}/{len(all_items_in_order)}",
        session=session,
        current_item=current_item,
        answer=research_answer,
        current_item_number=current_item_index + 1,
        total_items=len(all_items_in_order),
        progress_percent=progress_percent
    )

# We also need a route for the session summary. Let's add a placeholder for now.
@bp.route('/research_session/<int:session_id>/summary', methods=['GET'])
def view_research_session_summary(session_id):
    session = ResearchSession.query.get_or_404(session_id)
    # Fetch all answers for this session to display them
    answers = ResearchAnswer.query.filter_by(research_session_id=session.id).join(ChecklistItem).order_by(ChecklistItem.order).all()
    
    # To display answers in the correct checklist order, we might need the ordered list again
    # or ensure the 'answers' query is correctly ordered based on the item's original hierarchy and order.
    # For simplicity, the join and order by ChecklistItem.order might be sufficient for a basic summary.
    
    return render_template('main/session_summary.html', title="Research Summary", session=session, answers=answers)
