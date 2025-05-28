# company_research_platform/app/main/routes.py

from flask import render_template, request, redirect, url_for, flash # Added flash
from app import db
from app.models import User, Checklist, ChecklistItem # Ensure ChecklistItem is here
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
    # Fetch top-level items, already ordered by ChecklistItem.order
    top_level_items = checklist.items.filter_by(parent_id=None).order_by(ChecklistItem.order).all()

    return render_template(
        'main/view_checklist.html',
        checklist=checklist,
        items=top_level_items,
        title=checklist.name,
        ChecklistItem=ChecklistItem  # <--- ADD THIS LINE
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