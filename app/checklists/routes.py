from flask import render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from app import db
from app.models import User, Checklist, ChecklistItem, Company # Add Company if used in view_checklist for the form
from app.checklists import checklists_bp # Import the new blueprint


@checklists_bp.route('/')
@checklists_bp.route('/checklists', methods=['GET'])
@login_required 
def list_checklists():
    # Show checklists for the currently logged-in user
    checklists = Checklist.query.filter_by(user_id=current_user.id).order_by(Checklist.name).all()
    return render_template('list_checklists.html', checklists=checklists, title=f"{current_user.username}'s Checklists")

@checklists_bp.route('/checklists/new', methods=['GET', 'POST'])
@login_required
def new_checklist():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')

        if not name:
            flash('Checklist name is required!', 'error')
            # For GET request after error, redirect to GET to clear form method
            return redirect(url_for('checklists.new_checklist')) 

        new_checklist_obj = Checklist(name=name, description=description, author=current_user)
        db.session.add(new_checklist_obj)
        # It's often better to commit the parent object (checklist) first, 
        # or commit everything at the end. Let's commit at the end for this block.

        # Get initial item texts AND their corresponding LLM prompts
        item_texts = request.form.getlist('item_text[]')
        llm_prompts_for_items = request.form.getlist('item_llm_prompt[]') # New list of LLM prompts

        for i, text in enumerate(item_texts):
            if text.strip(): # Only add non-empty items
                # Get the corresponding LLM prompt, if available
                llm_prompt_text = None
                if i < len(llm_prompts_for_items) and llm_prompts_for_items[i].strip():
                    llm_prompt_text = llm_prompts_for_items[i].strip()

                item = ChecklistItem(
                    text=text, 
                    checklist=new_checklist_obj, 
                    order=i,
                    llm_prompt=llm_prompt_text # Save LLM prompt for initial item
                )
                db.session.add(item)

        try:
            db.session.commit() # Commit checklist and all its initial items
            flash('Checklist created successfully!', 'success')
            return redirect(url_for('checklists.view_checklist', checklist_id=new_checklist_obj.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating checklist: {str(e)}', 'error')
            # Re-render form with submitted values to allow correction
            return render_template('new_checklist.html', title="New Checklist", 
                                   name=name, description=description, 
                                   item_texts=item_texts, llm_prompts_for_items=llm_prompts_for_items)


    # For GET request or if POST had errors and re-renders with values
    # Get potential pre-filled values if re-rendering after a POST error
    name_val = request.form.get('name', '') if request.method == 'POST' else ''
    description_val = request.form.get('description', '') if request.method == 'POST' else ''
    item_texts_val = request.form.getlist('item_text[]') if request.method == 'POST' else ['','',''] # Default 3 empty for GET
    llm_prompts_val = request.form.getlist('item_llm_prompt[]') if request.method == 'POST' else ['','','']


    return render_template('new_checklist.html', title="New Checklist",
                           name=name_val, description=description_val,
                           item_texts=item_texts_val, # For re-population on POST error
                           llm_prompts_for_items=llm_prompts_val # For re-population on POST error
                           )

@checklists_bp.route('/<int:checklist_id>/view')
@login_required
def view_readonly_checklist(checklist_id):
    checklist = Checklist.query.get_or_404(checklist_id)
    if checklist.user_id != current_user.id:
        flash('You are not authorized to view this checklist.', 'error')
        return redirect(url_for('checklists.list_checklists'))

    top_level_items = checklist.items.filter_by(parent_id=None).order_by(ChecklistItem.order).all()
    user_companies = Company.query.filter_by(user_id=current_user.id).order_by(Company.name).all()
    
    return render_template(
        'view_readonly_checklist.html',
        checklist=checklist,
        items=top_level_items,
        title=checklist.name,
        ChecklistItem=ChecklistItem,
        companies=user_companies 
    )

@checklists_bp.route('/checklist_item/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_checklist_item(item_id):
    item_to_delete = ChecklistItem.query.get_or_404(item_id)

    # Authorization: Ensure the item belongs to a checklist owned by the current user
    checklist = item_to_delete.checklist # Access the parent checklist
    if checklist.user_id != current_user.id: # Or checklist.author != current_user
        flash('You are not authorized to delete items from this checklist.', 'error')
        # Redirect to a safe page, perhaps the checklists list or an error page
        return redirect(url_for('checklists.list_checklists'))

    # Store checklist_id for redirection before deleting the item
    parent_checklist_id = item_to_delete.checklist_id

    try:
        # SQLAlchemy will handle deleting child/sub-items due to 
        # cascade="all, delete-orphan" on the ChecklistItem.children relationship.
        db.session.delete(item_to_delete)
        db.session.commit()
        flash('Checklist item and its sub-items deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting checklist item: {str(e)}', 'error')

    return redirect(url_for('checklists.view_checklist', checklist_id=parent_checklist_id))
    
@checklists_bp.route('/checklists/<int:checklist_id>', methods=['GET'])
@login_required
def view_checklist(checklist_id):
    checklist = Checklist.query.get_or_404(checklist_id)
    if checklist.author != current_user: # Authorization check
        flash('You are not authorized to view this checklist.', 'error')
        return redirect(url_for('checklists.list_checklists'))
    top_level_items = checklist.items.filter_by(parent_id=None).order_by(ChecklistItem.order).all()
    user_companies = Company.query.filter_by(user_id=current_user.id).order_by(Company.name).all()
    
    return render_template(
        'view_checklist.html',
        checklist=checklist,
        items=top_level_items,  
        title=checklist.name,
        ChecklistItem=ChecklistItem, 
        companies=user_companies
    )
    
@checklists_bp.route('/checklists/<int:checklist_id>/add_item', methods=['POST'])
@login_required
def add_checklist_item(checklist_id):
    checklist = Checklist.query.get_or_404(checklist_id)
    if checklist.author != current_user: # Authorization check
        flash('You are not authorized to modify this checklist.', 'error')
        return redirect(url_for('checklists.list_checklists')) 

    # For simplicity, assume current user owns this or is default.
    # Add proper authorization later.

    item_text = request.form.get('item_text')
    parent_id_str = request.form.get('parent_id') # For sub-items
    llm_prompt_text = request.form.get('llm_prompt')
    
    parent_id = None
    if parent_id_str and parent_id_str.isdigit():
        parent_id = int(parent_id_str)
        # Ensure parent_id belongs to this checklist
        parent_item_check = ChecklistItem.query.filter_by(id=parent_id, checklist_id=checklist.id).first()
        if not parent_item_check:
            flash('Invalid parent item selected.', 'error')
            return redirect(url_for('checklists.view_checklist', checklist_id=checklist_id))

    if item_text:
        # Determine order for the new item
        if parent_id:
            current_max_order = db.session.query(db.func.max(ChecklistItem.order)).filter_by(checklist_id=checklist_id, parent_id=parent_id).scalar()
        else:
            current_max_order = db.session.query(db.func.max(ChecklistItem.order)).filter_by(checklist_id=checklist_id, parent_id=None).scalar()
        
        new_order = (current_max_order or -1) + 1

        new_item = ChecklistItem(text=item_text, 
                                 checklist_id=checklist.id, 
                                 parent_id=parent_id, 
                                 order=new_order,
                                 llm_prompt=llm_prompt_text if llm_prompt_text and llm_prompt_text.strip() else None # Save LLM prompt
                                 )
        db.session.add(new_item)
        db.session.commit()
        flash('Item added successfully!', 'success')
    else:
        flash('Item text cannot be empty.', 'error')
        
    return redirect(url_for('checklists.view_checklist', checklist_id=checklist_id))


@checklists_bp.route('/item/<int:item_id>/move/<direction>', methods=['POST'])
@login_required
def move_checklist_item(item_id, direction):
    item_to_move = ChecklistItem.query.get_or_404(item_id)
    checklist = item_to_move.checklist

    # Authorization: Ensure the item belongs to a checklist owned by the current user
    if checklist.user_id != current_user.id:
        flash('You are not authorized to modify this checklist.', 'error')
        return redirect(url_for('checklists.list_checklists'))

    # Fetch all siblings of the item, including itself, ordered by their current 'order'
    siblings = ChecklistItem.query.filter_by(
        checklist_id=item_to_move.checklist_id,
        parent_id=item_to_move.parent_id # Handles both top-level and sub-items
    ).order_by(ChecklistItem.order).all()

    try:
        current_index = siblings.index(item_to_move) # Find the item's current position
    except ValueError:
        # Should not happen if item_to_move is indeed a sibling
        flash('Error finding item in its sibling list.', 'error')
        return redirect(url_for('checklists.view_checklist', checklist_id=checklist.id))

    if direction == 'up':
        if current_index == 0: # Already at the top of its list
            flash('Item is already at the top.', 'info')
        else:
            # Item to swap with is the one before it
            item_above = siblings[current_index - 1]
            # Swap their order values
            item_to_move.order, item_above.order = item_above.order, item_to_move.order
            flash(f'Item "{item_to_move.text[:30]}..." moved up.', 'success')
    elif direction == 'down':
        if current_index == len(siblings) - 1: # Already at the bottom
            flash('Item is already at the bottom.', 'info')
        else:
            # Item to swap with is the one after it
            item_below = siblings[current_index + 1]
            # Swap their order values
            item_to_move.order, item_below.order = item_below.order, item_to_move.order
            flash(f'Item "{item_to_move.text[:30]}..." moved down.', 'success')
    else:
        flash('Invalid move direction.', 'error')
        return redirect(url_for('checklists.view_checklist', checklist_id=checklist.id))

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f'Error saving item order: {str(e)}', 'error')

    return redirect(url_for('checklists.view_checklist', checklist_id=checklist.id))


@checklists_bp.route('/item/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_checklist_item(item_id):
    item_to_edit = ChecklistItem.query.get_or_404(item_id)
    checklist = item_to_edit.checklist # Access the parent checklist

    # Authorization: Ensure the item belongs to a checklist owned by the current user
    if checklist.user_id != current_user.id: # Or checklist.author != current_user
        flash('You are not authorized to edit items from this checklist.', 'error')
        return redirect(url_for('checklists.list_checklists'))

    if request.method == 'POST':
        new_text = request.form.get('item_text')
        new_llm_prompt = request.form.get('llm_prompt')

        # Basic validation (you can add more)
        if not new_text or not new_text.strip():
            flash('Item text cannot be empty.', 'error')
            # Re-render the form with submitted values (which the template handles via request.form)
            return render_template('edit_checklist_item.html', title=f"Edit Item: {item_to_edit.text[:30]}...", item=item_to_edit)

        item_to_edit.text = new_text.strip()
        item_to_edit.llm_prompt = new_llm_prompt.strip() if new_llm_prompt and new_llm_prompt.strip() else None

        try:
            db.session.commit()
            flash('Checklist item updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating checklist item: {str(e)}', 'error')

        return redirect(url_for('checklists.view_checklist', checklist_id=checklist.id))

    # GET request: Display the form pre-filled with the item's current data
    return render_template('edit_checklist_item.html', 
                           title=f"Edit Item: {item_to_edit.text[:30]}...", 
                           item=item_to_edit)