# In app/logs/routes.py
from flask import render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from app import db
from app.models import MistakeLog, Checklist, ChecklistItem
from . import logs_bp
from sqlalchemy import func # Add func for the 'max' function

@logs_bp.route('/mistakes', methods=['GET', 'POST'])
@login_required
def mistake_log():
    if request.method == 'POST':
        description = request.form.get('mistake_description')
        source = request.form.get('source')
        lesson = request.form.get('lesson_learned')

        if not description or not lesson:
            flash('Mistake Description and Lesson Learned are required fields.', 'error')
        else:
            new_entry = MistakeLog(
                author=current_user,
                mistake_description=description,
                source=source,
                lesson_learned=lesson
            )
            db.session.add(new_entry)
            db.session.commit()
            flash('New lesson added to your Mistake Log.', 'success')

        return redirect(url_for('logs.mistake_log'))

    # GET Request: Fetch and display all log entries
    log_entries = MistakeLog.query.filter_by(user_id=current_user.id).order_by(MistakeLog.created_at.desc()).all()
    
    user_checklists = Checklist.query.filter_by(user_id=current_user.id).order_by(Checklist.name).all()

    return render_template('mistake_log.html', 
                           title="My Mistake Log",
                           log_entries=log_entries,
                           user_checklists=user_checklists)

# In app/logs/routes.py

@logs_bp.route('/mistake/<int:mistake_id>/add_to_checklists', methods=['POST']) # <-- Corrected line
@login_required
def add_to_checklists(mistake_id):
    mistake = MistakeLog.query.get_or_404(mistake_id)
    # Authorization check for the mistake log entry
    if mistake.author != current_user:
        flash("You are not authorized to perform this action.", "error")
        return redirect(url_for('logs.mistake_log'))

    # Get the list of checklist IDs from the form checkboxes
    selected_checklist_ids = request.form.getlist('checklist_ids', type=int)

    if not selected_checklist_ids:
        flash("You must select at least one checklist.", "warning")
        return redirect(url_for('logs.mistake_log'))
    
    lesson_text = mistake.lesson_learned
    added_count = 0

    for checklist_id in selected_checklist_ids:
        checklist = Checklist.query.get_or_404(checklist_id)
        # Authorization check for each checklist
        if checklist.author == current_user:
            # Logic to find the next order value for a new top-level item
            max_order = db.session.query(db.func.max(ChecklistItem.order)).filter_by(
                checklist_id=checklist.id,
                parent_id=None
            ).scalar()
            new_order = (max_order or -1) + 1

            # Create the new checklist item
            new_item = ChecklistItem(
                text=lesson_text,
                checklist_id=checklist.id,
                order=new_order
                # author=current_user # This line may or may not be needed depending on your final ChecklistItem model
            )
            db.session.add(new_item)
            added_count += 1
    
    if added_count > 0:
        db.session.commit()
        flash(f'Successfully added lesson to {added_count} checklist(s).', 'success')
    
    return redirect(url_for('logs.mistake_log'))