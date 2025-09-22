from flask import render_template, request, redirect, url_for, flash, jsonify, send_from_directory, abort
from flask_login import current_user, login_required
from app import db
from app.models import (JournalEntry, ThesisEvolution, LearningNote,
                       JournalTemplate, JournalAttachment, Company,
                       ResearchProject)
from app.journal_enhanced import journal_enhanced_bp
from app.journal_enhanced.utils import (extract_tags_from_content, get_related_entries,
                                       get_review_queue, update_thesis_version,
                                       calculate_next_review_date, search_journal,
                                      get_all_user_tags,
                                       get_journal_statistics, create_default_templates)
from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename
import json

# File upload configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'xlsx', 'xls', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@journal_enhanced_bp.route('/')
@login_required
def journal_home():
    """Main journal dashboard"""
    # Get recent entries
    recent_entries = current_user.journal_entries.filter_by(is_archived=False)\
                                                 .order_by(JournalEntry.created_at.desc())\
                                                 .limit(10).all()
    
    # Get review queue
    review_queue = get_review_queue(current_user.id)
    
    # Get statistics
    stats = get_journal_statistics(current_user.id)
    
    # Get starred entries
    starred_entries = current_user.journal_entries.filter_by(is_starred=True, is_archived=False)\
                                                  .order_by(JournalEntry.created_at.desc())\
                                                  .limit(5).all()
    
    # Get active companies for quick entry
    active_companies = Company.query.join(ResearchProject).filter(
        ResearchProject.user_id == current_user.id,
        ResearchProject.status == 'active'
    ).distinct().all()
    
    return render_template('journal_home.html',
                          title="Research Journal",
                          recent_entries=recent_entries,
                          review_queue=review_queue,
                          stats=stats,
                          starred_entries=starred_entries,
                          active_companies=active_companies)

@journal_enhanced_bp.route('/entry/new', methods=['GET', 'POST'])
@login_required
def new_entry():
    """Create a new journal entry"""
    if request.method == 'POST':
        title = request.form.get('title')
        entry_type = request.form.get('entry_type', 'observation')
        content = request.form.get('content')
        key_insight = request.form.get('key_insight')
        sentiment = request.form.get('sentiment')
        conviction = request.form.get('conviction', type=int)
        company_id = request.form.get('company_id', type=int)
        
        if not content:
            flash('Content is required', 'error')
            return redirect(url_for('journal_enhanced.new_entry'))
        
        # Extract tags from content
        tags = extract_tags_from_content(content)
        
        # Parse action items and questions
        action_items = request.form.get('action_items', '').split('\n')
        action_items = [item.strip() for item in action_items if item.strip()]
        
        questions = request.form.get('questions_raised', '').split('\n')
        questions = [q.strip() for q in questions if q.strip()]
        
        entry = JournalEntry(
            author=current_user,
            title=title,
            entry_type=entry_type,
            content=content,
            key_insight=key_insight,
            sentiment=sentiment,
            conviction_level=conviction,
            company_id=company_id if company_id else None,
            tags=tags,
            action_items=action_items if action_items else None,
            questions_raised=questions if questions else None,
            source=request.form.get('source')
        )
        
        # Link to active research project if exists
        if company_id:
            active_project = ResearchProject.query.filter_by(
                user_id=current_user.id,
                company_id=company_id,
                status='active'
            ).first()
            if active_project:
                entry.project_id = active_project.id
        
        db.session.add(entry)
        
        # Handle file attachments
        if 'attachments' in request.files:
            files = request.files.getlist('attachments')
            for file in files:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    # Create upload directory if it doesn't exist
                    upload_dir = os.path.join('app', 'static', 'uploads', 'journal', str(current_user.id))
                    os.makedirs(upload_dir, exist_ok=True)
                    
                    # Save file with timestamp to avoid conflicts
                    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                    filename = f"{timestamp}_{filename}"
                    filepath = os.path.join(upload_dir, filename)
                    file.save(filepath)
                    
                    # Create attachment record
                    # Store relative path for URL generation
                    relative_path = f"uploads/journal/{current_user.id}/{filename}"
                    attachment = JournalAttachment(
                        entry=entry,
                        filename=filename,
                        file_type=filename.rsplit('.', 1)[1].lower(),
                        file_path=relative_path,
                        file_size=os.path.getsize(filepath)
                    )
                    db.session.add(attachment)
        
        try:
            db.session.commit()
            
            # Check if this should update thesis
            if entry_type == 'thesis_update' and company_id:
                update_thesis_version(
                    current_user.id,
                    company_id,
                    content,
                    trigger='Journal entry'
                )
            
            flash('Journal entry created successfully!', 'success')
            return redirect(url_for('journal_enhanced.journal_home'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating entry: {str(e)}', 'error')
    
    # Get templates
    templates = JournalTemplate.query.filter(
        db.or_(
            JournalTemplate.user_id == current_user.id,
            JournalTemplate.is_public == True
        )
    ).filter_by(is_active=True).all()
    
    # Get companies for dropdown
    companies = current_user.companies.order_by(Company.name).all()
    
    # Get template from query param if specified
    template_id = request.args.get('template_id', type=int)
    selected_template = None
    if template_id:
        selected_template = JournalTemplate.query.get(template_id)
    
    # Get company from query param if specified (for quick entry)
    company_id = request.args.get('company_id', type=int)
    
    return render_template('new_entry.html',
                          title="New Journal Entry",
                          templates=templates,
                          companies=companies,
                          selected_template=selected_template,
                          preset_company_id=company_id)

@journal_enhanced_bp.route('/entry/<int:entry_id>')
@login_required
def entry_detail(entry_id):
    """View journal entry details"""
    entry = JournalEntry.query.get_or_404(entry_id)
    
    if entry.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('journal_enhanced.journal_home'))
    
    # Don't automatically mark as reviewed - let user control this manually
    
    # Get related entries
    related_entries = get_related_entries(entry, limit=5)
    
    # Get attachments
    attachments = entry.attachments.all()
    
    return render_template('entry_detail.html',
                            title=entry.title or "Journal Entry",
                            entry=entry,
                            related_entries=related_entries,
                            attachments=attachments)   
@journal_enhanced_bp.route('/entry/<int:entry_id>/edit', methods=['GET', 'POST'])

@login_required
def edit_entry(entry_id):
   """Edit a journal entry"""
   entry = JournalEntry.query.get_or_404(entry_id)
   
   if entry.user_id != current_user.id:
       flash('Access denied', 'error')
       return redirect(url_for('journal_enhanced.journal_home'))
   
   if request.method == 'POST':
       entry.title = request.form.get('title')
       entry.content = request.form.get('content')
       entry.key_insight = request.form.get('key_insight')
       entry.sentiment = request.form.get('sentiment')
       entry.conviction_level = request.form.get('conviction', type=int)
       
       # Update tags
       entry.tags = extract_tags_from_content(entry.content)
       
       # Update action items and questions
       action_items = request.form.get('action_items', '').split('\n')
       entry.action_items = [item.strip() for item in action_items if item.strip()]
       
       questions = request.form.get('questions_raised', '').split('\n')
       entry.questions_raised = [q.strip() for q in questions if q.strip()]
       
       entry.updated_at = datetime.utcnow()
       
       try:
           db.session.commit()
           flash('Entry updated successfully!', 'success')
           return redirect(url_for('journal_enhanced.entry_detail', entry_id=entry.id))
       except Exception as e:
           db.session.rollback()
           flash(f'Error updating entry: {str(e)}', 'error')
   
   companies = current_user.companies.order_by(Company.name).all()
   
   return render_template('edit_entry.html',
                         title="Edit Entry",
                         entry=entry,
                         companies=companies)

@journal_enhanced_bp.route('/entry/<int:entry_id>/star', methods=['POST'])
@login_required
def toggle_star(entry_id):
   """Toggle star status of an entry"""
   entry = JournalEntry.query.get_or_404(entry_id)
   
   if entry.user_id != current_user.id:
       return jsonify({'error': 'Access denied'}), 403
   
   entry.is_starred = not entry.is_starred
   
   try:
       db.session.commit()
       return jsonify({'starred': entry.is_starred})
   except Exception as e:
       db.session.rollback()
       return jsonify({'error': str(e)}), 500

@journal_enhanced_bp.route('/entry/<int:entry_id>/archive', methods=['POST'])
@login_required
def archive_entry(entry_id):
   """Archive a journal entry"""
   entry = JournalEntry.query.get_or_404(entry_id)
   
   if entry.user_id != current_user.id:
       flash('Access denied', 'error')
       return redirect(url_for('journal_enhanced.journal_home'))
   
   entry.is_archived = True
   
   try:
       db.session.commit()
       flash('Entry archived', 'info')
   except Exception as e:
       db.session.rollback()
       flash(f'Error archiving entry: {str(e)}', 'error')
   
   return redirect(url_for('journal_enhanced.journal_home'))

@journal_enhanced_bp.route('/thesis-evolution/<int:company_id>')
@login_required
def thesis_evolution(company_id):
   """View thesis evolution for a company"""
   company = Company.query.get_or_404(company_id)
   
   if company.user_id != current_user.id:
       flash('Access denied', 'error')
       return redirect(url_for('companies.companies_dashboard'))
   
   # Get all thesis versions
   thesis_versions = ThesisEvolution.query.filter_by(
       user_id=current_user.id,
       company_id=company_id
   ).order_by(ThesisEvolution.version.desc()).all()
   
   # Get related journal entries
   thesis_entries = JournalEntry.query.filter_by(
       user_id=current_user.id,
       company_id=company_id,
       entry_type='thesis_update'
   ).order_by(JournalEntry.created_at.desc()).all()
   
   # Prepare chart data for conviction over time
   conviction_data = []
   for version in reversed(thesis_versions):
       if version.conviction_level:
           conviction_data.append({
               'date': version.created_at.strftime('%Y-%m-%d'),
               'conviction': version.conviction_level,
               'version': version.version
           })
   
   return render_template('thesis_evolution.html',
                         title=f"Thesis Evolution: {company.name}",
                         company=company,
                         thesis_versions=thesis_versions,
                         thesis_entries=thesis_entries,
                         conviction_data=json.dumps(conviction_data))

@journal_enhanced_bp.route('/thesis-evolution/<int:company_id>/new', methods=['GET', 'POST'])
@login_required
def new_thesis_version(company_id):
   """Create a new thesis version"""
   company = Company.query.get_or_404(company_id)
   
   if company.user_id != current_user.id:
       flash('Access denied', 'error')
       return redirect(url_for('companies.companies_dashboard'))
   
   if request.method == 'POST':
       thesis = request.form.get('thesis')
       conviction = request.form.get('conviction_level', type=int)
       position_sizing = request.form.get('position_sizing')
       change_trigger = request.form.get('change_trigger')
       change_summary = request.form.get('change_summary')
       
       # Parse bull and bear cases
       bull_case = request.form.get('bull_case', '').split('\n')
       bull_case = [point.strip() for point in bull_case if point.strip()]
       
       bear_case = request.form.get('bear_case', '').split('\n')
       bear_case = [point.strip() for point in bear_case if point.strip()]
       
       # Get key metrics
       key_metrics = {}
       metric_names = request.form.getlist('metric_name[]')
       metric_values = request.form.getlist('metric_value[]')
       for name, value in zip(metric_names, metric_values):
           if name and value:
               key_metrics[name] = value
       
       # Create new version
       thesis_evolution = update_thesis_version(
           current_user.id,
           company_id,
           thesis,
           trigger=change_trigger
       )
       
       if thesis_evolution:
           thesis_evolution.conviction_level = conviction
           thesis_evolution.position_sizing = position_sizing
           thesis_evolution.change_summary = change_summary
           thesis_evolution.bull_case = bull_case
           thesis_evolution.bear_case = bear_case
           thesis_evolution.key_metrics = key_metrics
           
           # Create corresponding journal entry
           journal_entry = JournalEntry(
               author=current_user,
               title=f"Thesis Update: {company.name}",
               entry_type='thesis_update',
               content=thesis,
               key_insight=change_summary,
               conviction_level=conviction,
               company_id=company_id,
               sentiment='bullish' if conviction >= 7 else 'neutral' if conviction >= 4 else 'bearish'
           )
           db.session.add(journal_entry)
           thesis_evolution.linked_journal_entry_id = journal_entry.id
           
           try:
               db.session.commit()
               flash('Thesis updated successfully!', 'success')
               return redirect(url_for('journal_enhanced.thesis_evolution', company_id=company_id))
           except Exception as e:
               db.session.rollback()
               flash(f'Error updating thesis: {str(e)}', 'error')
   
   # Get current thesis for reference
   current_thesis = ThesisEvolution.query.filter_by(
       user_id=current_user.id,
       company_id=company_id,
       is_current=True
   ).first()
   
   return render_template('new_thesis_version.html',
                         title=f"Update Thesis: {company.name}",
                         company=company,
                         current_thesis=current_thesis)

@journal_enhanced_bp.route('/learning-notes')
@login_required
def learning_notes():
   """View and manage learning notes"""
   # Get all learning notes
   notes = current_user.learning_notes.order_by(
       LearningNote.importance.desc(),
       LearningNote.created_at.desc()
   ).all()
   
   # Categorize notes
   categories = {}
   for note in notes:
       category = note.category or 'Uncategorized'
       if category not in categories:
           categories[category] = []
       categories[category].append(note)
   
   # Get notes due for review
   due_for_review = current_user.learning_notes.filter(
       LearningNote.next_review_date <= datetime.utcnow().date()
   ).count()
   
   return render_template('learning_notes.html',
                         title="Learning Notes",
                         notes=notes,
                         categories=categories,
                         due_for_review=due_for_review)

@journal_enhanced_bp.route('/learning-notes/new', methods=['GET', 'POST'])
@login_required
def new_learning_note():
   """Create a new learning note"""
   if request.method == 'POST':
       title = request.form.get('title')
       lesson = request.form.get('lesson')
       category = request.form.get('category')
       context = request.form.get('context')
       how_to_apply = request.form.get('how_to_apply')
       importance = request.form.get('importance', type=int)
       company_id = request.form.get('company_id', type=int)
       
       if not title or not lesson:
           flash('Title and lesson are required', 'error')
           return redirect(url_for('journal_enhanced.new_learning_note'))
       
       # Parse examples
       examples = request.form.get('examples', '').split('\n')
       examples = [ex.strip() for ex in examples if ex.strip()]
       
       note = LearningNote(
           author=current_user,
           title=title,
           lesson=lesson,
           category=category,
           context=context,
           how_to_apply=how_to_apply,
           importance=importance or 5,
           examples=examples if examples else None,
           company_id=company_id if company_id else None,
           source_type=request.form.get('source_type'),
           source_detail=request.form.get('source_detail'),
           next_review_date=datetime.utcnow().date() + timedelta(days=1)
       )
       
       # Extract tags
       note.tags = extract_tags_from_content(lesson)
       
       db.session.add(note)
       
       try:
           db.session.commit()
           flash('Learning note created!', 'success')
           return redirect(url_for('journal_enhanced.learning_notes'))
       except Exception as e:
           db.session.rollback()
           flash(f'Error creating note: {str(e)}', 'error')
   
   companies = current_user.companies.order_by(Company.name).all()
   
   return render_template('new_learning_note.html',
                         title="New Learning Note",
                         companies=companies)

@journal_enhanced_bp.route('/learning-notes/<int:note_id>/review', methods=['POST'])
@login_required
def review_learning_note(note_id):
   """Mark a learning note as reviewed"""
   note = LearningNote.query.get_or_404(note_id)
   
   if note.user_id != current_user.id:
       return jsonify({'error': 'Access denied'}), 403
   
   note.times_reviewed += 1
   note.last_reviewed = datetime.utcnow()
   note.next_review_date = calculate_next_review_date(note)
   
   try:
       db.session.commit()
       return jsonify({
           'success': True,
           'times_reviewed': note.times_reviewed,
           'next_review': note.next_review_date.strftime('%Y-%m-%d')
       })
   except Exception as e:
       db.session.rollback()
       return jsonify({'error': str(e)}), 500

@journal_enhanced_bp.route('/review-queue')
@login_required
def review_queue():
   """Show items due for review"""
   queue = get_review_queue(current_user.id)

   return render_template('review_queue.html',
                         title="Review Queue",
                         learning_notes=queue['learning_notes'],
                         pending_entries=queue['pending_entries'],
                         starred_entries=queue['starred_entries'],
                         total_items=queue['total_items'])

@journal_enhanced_bp.route('/search')
@login_required
def search():
    """Enhanced search for knowledge hub with advanced filtering"""
    query = request.args.get('q', '')
    company_id = request.args.get('company_id', type=int)
    entry_type = request.args.get('entry_type')
    sentiment = request.args.get('sentiment')
    starred_only = request.args.get('starred_only') == 'true'
    reviewed_only = request.args.get('reviewed_only') == 'true'
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    review_date_from = request.args.get('review_date_from')
    review_date_to = request.args.get('review_date_to')
    selected_tags = request.args.getlist('tags')

    filters = {}
    if company_id:
        filters['company_id'] = company_id
    if entry_type:
        filters['entry_type'] = entry_type
    if sentiment:
        filters['sentiment'] = sentiment
    if starred_only:
        filters['starred_only'] = True
    if reviewed_only:
        filters['reviewed_only'] = True
    if date_from:
        filters['date_from'] = datetime.strptime(date_from, '%Y-%m-%d')
    if date_to:
        filters['date_to'] = datetime.strptime(date_to, '%Y-%m-%d')
    if review_date_from:
        filters['review_date_from'] = datetime.strptime(review_date_from, '%Y-%m-%d')
    if review_date_to:
        filters['review_date_to'] = datetime.strptime(review_date_to, '%Y-%m-%d')
    if selected_tags:
        filters['tags'] = selected_tags

    results = search_journal(current_user.id, query, filters)

    # Get all available tags for the filter UI
    all_tags = get_all_user_tags(current_user.id)

    # Get companies for filter dropdown
    companies = current_user.companies.order_by(Company.name).all()

    # Get entry types
    entry_types = db.session.query(JournalEntry.entry_type.distinct()).filter_by(
        user_id=current_user.id
    ).all()
    entry_types = [t[0] for t in entry_types]

    return render_template('search_results.html',
                          title="Knowledge Hub Search",
                          query=query,
                          results=results,
                          filters=request.args.to_dict(flat=False),
                          selected_tags=selected_tags,
                          all_tags=all_tags,
                          companies=companies,
                          entry_types=entry_types)

@journal_enhanced_bp.route('/templates')
@login_required
def manage_templates():
   """Manage journal templates"""
   # Get user's templates
   user_templates = current_user.journal_templates.filter_by(is_active=True).all()
   
   # Get public templates
   public_templates = JournalTemplate.query.filter_by(
       user_id=None,
       is_public=True,
       is_active=True
   ).all()
   
   # Create default templates if none exist
   if not public_templates:
       public_templates = create_default_templates()
   
   return render_template('manage_templates.html',
                         title="Journal Templates",
                         user_templates=user_templates,
                         public_templates=public_templates)

@journal_enhanced_bp.route('/export')
@login_required
def export_journal():
   """Export journal entries"""
   format_type = request.args.get('format', 'json')
   company_id = request.args.get('company_id', type=int)
   
   # Get entries to export
   query = current_user.journal_entries
   if company_id:
       query = query.filter_by(company_id=company_id)
   
   entries = query.order_by(JournalEntry.created_at.desc()).all()
   
   if format_type == 'json':
       # Export as JSON
       export_data = []
       for entry in entries:
           export_data.append({
               'title': entry.title,
               'type': entry.entry_type,
               'content': entry.content,
               'key_insight': entry.key_insight,
               'sentiment': entry.sentiment,
               'conviction_level': entry.conviction_level,
               'company': entry.company.name if entry.company else None,
               'tags': entry.tags,
               'created_at': entry.created_at.isoformat(),
               'action_items': entry.action_items,
               'questions_raised': entry.questions_raised
           })
       
       return jsonify(export_data)
   
   # Could add CSV, Markdown, or other formats
   flash('Export format not supported', 'error')
   return redirect(url_for('journal_enhanced.journal_home'))

@journal_enhanced_bp.route('/attachment/<int:attachment_id>')
@login_required
def view_attachment(attachment_id):
    """Serve attachment files for viewing/downloading"""
    attachment = JournalAttachment.query.get_or_404(attachment_id)
    
    # Security check: ensure user owns the journal entry
    if attachment.entry.user_id != current_user.id:
        abort(403)
    
    # Get the file path
    if attachment.file_path:
        file_path = attachment.file_path
    else:
        # Fallback to constructed path
        file_path = f"uploads/journal/{current_user.id}/{attachment.filename}"
    
    # Full file path
    full_path = os.path.join(os.getcwd(), 'app', 'static', file_path)
    
    if not os.path.exists(full_path):
        flash('Attachment file not found', 'error')
        abort(404)
    
    # Get directory and filename
    directory = os.path.dirname(full_path)
    filename = os.path.basename(full_path)
    
    try:
        return send_from_directory(directory, filename, as_attachment=False)
    except Exception as e:
        flash('Error accessing attachment', 'error')
        abort(500)

@journal_enhanced_bp.route('/attachment/<int:attachment_id>/download')
@login_required  
def download_attachment(attachment_id):
    """Download attachment files"""
    attachment = JournalAttachment.query.get_or_404(attachment_id)
    
    # Security check: ensure user owns the journal entry
    if attachment.entry.user_id != current_user.id:
        abort(403)
    
    # Get the file path
    if attachment.file_path:
        file_path = attachment.file_path
    else:
        # Fallback to constructed path
        file_path = f"uploads/journal/{current_user.id}/{attachment.filename}"
    
    # Full file path
    full_path = os.path.join(os.getcwd(), 'app', 'static', file_path)
    
    if not os.path.exists(full_path):
        flash('Attachment file not found', 'error')
        abort(404)
    
    # Get directory and filename
    directory = os.path.dirname(full_path)
    filename = os.path.basename(full_path)
    
    try:
        return send_from_directory(directory, filename, as_attachment=True)
    except Exception as e:
        flash('Error downloading attachment', 'error')
        abort(500)

@journal_enhanced_bp.route('/entry/<int:entry_id>/delete', methods=['POST'])
@login_required
def delete_entry(entry_id):
    """Delete a journal entry"""
    entry = JournalEntry.query.get_or_404(entry_id)

    # Security check: ensure user owns the entry
    if entry.user_id != current_user.id:
        flash('Access denied', 'error')
        abort(403)

    try:
        # Delete associated attachments and their files
        for attachment in entry.attachments:
            # Delete the file from filesystem
            if attachment.file_path:
                full_path = os.path.join(os.getcwd(), 'app', 'static', attachment.file_path)
                if os.path.exists(full_path):
                    os.remove(full_path)

        # Delete the entry (cascades to attachments)
        db.session.delete(entry)
        db.session.commit()

        flash('Journal entry deleted successfully', 'success')
        return redirect(url_for('journal_enhanced.journal_home'))

    except Exception as e:
        db.session.rollback()
        flash('Error deleting entry', 'error')
        return redirect(url_for('journal_enhanced.entry_detail', entry_id=entry_id))

@journal_enhanced_bp.route('/entry/<int:entry_id>/mark_pending', methods=['POST'])
@login_required
def mark_entry_pending(entry_id):
    """Mark entry as pending review"""
    entry = JournalEntry.query.get_or_404(entry_id)

    # Security check: ensure user owns the entry
    if entry.user_id != current_user.id:
        flash('Access denied', 'error')
        abort(403)

    try:
        entry.last_reviewed = None
        db.session.commit()
        flash('Entry marked as pending review', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error updating entry status', 'error')

    return redirect(url_for('journal_enhanced.entry_detail', entry_id=entry_id))

@journal_enhanced_bp.route('/entry/<int:entry_id>/review', methods=['POST'])
@login_required
def review_entry(entry_id):
    """Enhanced review entry with notes and knowledge tags"""
    entry = JournalEntry.query.get_or_404(entry_id)

    # Security check: ensure user owns the entry
    if entry.user_id != current_user.id:
        flash('Access denied', 'error')
        abort(403)

    try:
        from datetime import datetime

        # Update review information
        entry.last_reviewed = datetime.utcnow()
        entry.review_count += 1

        # Add review notes if provided
        review_notes = request.form.get('review_notes', '').strip()
        if review_notes:
            entry.review_notes = review_notes

        # Handle knowledge tags
        knowledge_tags = request.form.get('knowledge_tags', '').strip()
        if knowledge_tags:
            # Parse knowledge tags and add to existing tags
            new_tags = [tag.strip() for tag in knowledge_tags.split(',') if tag.strip()]
            existing_tags = entry.tags or []

            # Merge tags, avoiding duplicates
            all_tags = list(set(existing_tags + new_tags))
            entry.tags = all_tags

        db.session.commit()
        flash('Entry reviewed successfully! Added to your knowledge base.', 'success')

        # Return JSON response for AJAX calls, otherwise redirect
        if request.headers.get('Content-Type') == 'application/json':
            return jsonify({
                'success': True,
                'message': 'Entry reviewed successfully',
                'review_count': entry.review_count,
                'last_reviewed': entry.last_reviewed.strftime('%Y-%m-%d %H:%M')
            })

    except Exception as e:
        db.session.rollback()
        flash('Error reviewing entry', 'error')

        if request.headers.get('Content-Type') == 'application/json':
            return jsonify({'success': False, 'message': str(e)}), 500

    return redirect(url_for('journal_enhanced.entry_detail', entry_id=entry_id))

@journal_enhanced_bp.route('/entry/<int:entry_id>/mark_reviewed', methods=['POST'])
@login_required
def mark_entry_reviewed(entry_id):
    """Quick mark entry as reviewed (for backward compatibility)"""
    entry = JournalEntry.query.get_or_404(entry_id)

    # Security check: ensure user owns the entry
    if entry.user_id != current_user.id:
        flash('Access denied', 'error')
        abort(403)

    try:
        from datetime import datetime
        entry.last_reviewed = datetime.utcnow()
        entry.review_count += 1
        db.session.commit()
        flash('Entry marked as reviewed', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error updating entry status', 'error')

    return redirect(url_for('journal_enhanced.entry_detail', entry_id=entry_id))