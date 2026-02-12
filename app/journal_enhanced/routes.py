from flask import render_template, request, redirect, url_for, flash, jsonify, send_from_directory, abort, session
from flask_login import current_user, login_required
from app import db
from app.models import (JournalEntry, ThesisEvolution, LearningNote,
                       JournalTemplate, JournalAttachment, Company,
                       ResearchProject)
from app.journal_enhanced import journal_enhanced_bp
from app.journal_enhanced.utils import (extract_tags_from_content, get_related_entries,
                                       get_review_queue, update_thesis_version,
                                       calculate_next_review_date, create_default_templates)
from app.utils.time_utils import now_utc
from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename
import json
import logging
from app.services.research_journal_intelligence import (
    analyze_journal_entry,
    detect_thesis_contradictions,
    find_related_entries as ai_find_related_entries
)

logger = logging.getLogger(__name__)

# File upload configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'xlsx', 'xls', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@journal_enhanced_bp.route('/entry/new', methods=['GET', 'POST'])
@login_required
def new_entry():
    """Create a new journal entry"""
    if request.method == 'POST':
        title = request.form.get('title')

        # Handle custom entry type
        entry_type = request.form.get('entry_type', 'observation')
        if entry_type == 'custom':
            custom_entry_type = request.form.get('custom_entry_type', '').strip()
            entry_type = custom_entry_type if custom_entry_type else 'other'

        content = request.form.get('content')
        key_insight = request.form.get('key_insight')
        sentiment = request.form.get('sentiment')
        conviction = request.form.get('conviction', type=int)
        company_id = request.form.get('company_id', type=int)

        if not content:
            flash('Content is required', 'error')
            return redirect(url_for('journal_enhanced.new_entry'))

        # Extract tags from content
        auto_tags = extract_tags_from_content(content)

        # Parse hashtags
        hashtags_str = request.form.get('hashtags', '').strip()
        hashtags = []
        if hashtags_str:
            # Split by spaces and commas, remove # prefix (store without #)
            raw_tags = hashtags_str.replace(',', ' ').split()
            hashtags = [tag.lstrip('#') for tag in raw_tags if tag.strip()]

        # Merge auto-extracted tags with user-provided hashtags (all without # prefix)
        all_tags = auto_tags + hashtags if hashtags else auto_tags
        # Remove # from auto_tags too and deduplicate
        tags = list(set(tag.lstrip('#') for tag in all_tags))
        
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
                    timestamp = now_utc().strftime('%Y%m%d_%H%M%S')
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
            return redirect(url_for('journal_enhanced.knowledge_hub', view='research'))
            
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
        return redirect(url_for('journal_enhanced.knowledge_hub', view='research'))

    # Don't automatically mark as reviewed - let user control this manually
    
    # Get related entries using existing rule-based function
    related_entries = get_related_entries(entry)
    
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
       return redirect(url_for('journal_enhanced.knowledge_hub', view='research'))

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
       
       entry.updated_at = now_utc
       
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
       return redirect(url_for('journal_enhanced.knowledge_hub', view='research'))

   entry.is_archived = True
   
   try:
       db.session.commit()
       flash('Entry archived', 'info')
   except Exception as e:
       db.session.rollback()
       flash(f'Error archiving entry: {str(e)}', 'error')

   return redirect(url_for('journal_enhanced.knowledge_hub', view='research'))

@journal_enhanced_bp.route('/thesis-evolution/<int:company_id>')
@login_required
def thesis_evolution(company_id):
   """View thesis evolution for a company"""
   company = Company.query.get_or_404(company_id)
   
   if company.user_id != current_user.id:
       flash('Access denied', 'error')
       return redirect(url_for('companies.list_companies'))
   
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
       return redirect(url_for('companies.list_companies'))
   
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

@journal_enhanced_bp.route('/learning-notes/new', methods=['GET', 'POST'])
@login_required
def new_learning_note():
   """Create a new learning note"""
   if request.method == 'POST':
       title = request.form.get('title')
       lesson = request.form.get('lesson')

       # Handle custom category
       category = request.form.get('category')
       if category == 'custom':
           custom_category = request.form.get('custom_category', '').strip()
           category = custom_category if custom_category else 'other'

       knowledge_type = request.form.get('knowledge_type')
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

       # Parse topic tags
       topic_tags_str = request.form.get('topic_tags', '')
       topic_tags = [tag.strip() for tag in topic_tags_str.split(',') if tag.strip()] if topic_tags_str else None

       # Parse hashtags
       hashtags_str = request.form.get('hashtags', '').strip()
       hashtags = []
       if hashtags_str:
           # Split by spaces and commas, remove # prefix (store without #)
           raw_tags = hashtags_str.replace(',', ' ').split()
           hashtags = [tag.lstrip('#') for tag in raw_tags if tag.strip()]

       # Parse investor tags - automatically use source_author if provided
       source_author = request.form.get('source_author')
       investor_tags = [source_author] if source_author else None

       # Parse source date
       source_date = None
       source_date_str = request.form.get('source_date')
       if source_date_str:
           try:
               source_date = datetime.strptime(source_date_str, '%Y-%m-%d').date()
           except ValueError:
               pass

       note = LearningNote(
           author=current_user,
           title=title,
           lesson=lesson,
           category=category,
           knowledge_type=knowledge_type,
           context=context,
           how_to_apply=how_to_apply,
           importance=importance or 5,
           examples=examples if examples else None,
           company_id=company_id if company_id else None,
           source_type=request.form.get('source_type'),
           source_detail=request.form.get('source_detail'),
           source_url=request.form.get('source_url'),
           source_author=request.form.get('source_author'),
           source_date=source_date,
           topic_tags=topic_tags,
           investor_tags=investor_tags,
           next_review_date=now_utc().date() + timedelta(days=1)
       )

       # Extract and combine tags
       auto_tags = extract_tags_from_content(lesson)
       # Merge auto-extracted tags with user-provided hashtags (all without # prefix)
       all_tags = auto_tags + hashtags if hashtags else auto_tags
       # Remove # from all tags and deduplicate
       note.tags = list(set(tag.lstrip('#') for tag in all_tags))

       db.session.add(note)

       try:
           db.session.commit()
           flash('Learning note created!', 'success')
           return redirect(url_for('journal_enhanced.knowledge_hub', view='wisdom'))
       except Exception as e:
           db.session.rollback()
           flash(f'Error creating note: {str(e)}', 'error')

   companies = current_user.companies.order_by(Company.name).all()

   return render_template('new_learning_note.html',
                         title="New Learning Note",
                         companies=companies)

@journal_enhanced_bp.route('/learning-notes/<int:note_id>')
@login_required
def learning_note_detail(note_id):
   """View learning note detail"""
   note = LearningNote.query.get_or_404(note_id)

   if note.user_id != current_user.id:
       flash('Access denied', 'error')
       return redirect(url_for('journal_enhanced.knowledge_hub', view='wisdom'))

   # Auto-track review: Update last_reviewed when user views the insight
   note.last_reviewed = now_utc()
   note.times_reviewed = (note.times_reviewed or 0) + 1

   try:
       db.session.commit()
   except Exception as e:
       db.session.rollback()
       logger.error(f"Error tracking review for learning note {note_id}: {str(e)}")

   return render_template('learning_note_detail.html',
                         title=note.title,
                         note=note)

@journal_enhanced_bp.route('/learning-notes/<int:note_id>/review', methods=['POST'])
@login_required
def review_learning_note(note_id):
   """Mark a learning note as reviewed"""
   note = LearningNote.query.get_or_404(note_id)

   if note.user_id != current_user.id:
       return jsonify({'error': 'Access denied'}), 403

   note.times_reviewed += 1
   note.last_reviewed = now_utc()
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

@journal_enhanced_bp.route('/learning-notes/<int:note_id>/toggle-favorite', methods=['POST'])
@login_required
def toggle_favorite_note(note_id):
   """Toggle favorite status of a learning note"""
   note = LearningNote.query.get_or_404(note_id)

   if note.user_id != current_user.id:
       return jsonify({'error': 'Access denied'}), 403

   note.is_favorite = not note.is_favorite

   try:
       db.session.commit()
       return jsonify({'success': True, 'is_favorite': note.is_favorite})
   except Exception as e:
       db.session.rollback()
       return jsonify({'error': str(e)}), 500

@journal_enhanced_bp.route('/learning-notes/<int:note_id>/delete', methods=['POST'])
@login_required
def delete_learning_note(note_id):
   """Delete a learning note"""
   note = LearningNote.query.get_or_404(note_id)

   if note.user_id != current_user.id:
       return jsonify({'error': 'Access denied'}), 403

   try:
       db.session.delete(note)
       db.session.commit()
       return jsonify({'success': True})
   except Exception as e:
       db.session.rollback()
       return jsonify({'error': str(e)}), 500

@journal_enhanced_bp.route('/learning-notes/<int:note_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_learning_note(note_id):
   """Edit a learning note"""
   note = LearningNote.query.get_or_404(note_id)

   if note.user_id != current_user.id:
       flash('Access denied', 'error')
       return redirect(url_for('journal_enhanced.knowledge_hub', view='wisdom'))

   if request.method == 'POST':
       note.title = request.form.get('title')
       note.lesson = request.form.get('lesson')
       note.category = request.form.get('category')
       note.knowledge_type = request.form.get('knowledge_type')
       note.context = request.form.get('context')
       note.how_to_apply = request.form.get('how_to_apply')
       note.importance = request.form.get('importance', type=int)
       note.source_type = request.form.get('source_type')
       note.source_detail = request.form.get('source_detail')
       note.source_url = request.form.get('source_url')
       note.source_author = request.form.get('source_author')

       # Parse source date
       source_date_str = request.form.get('source_date')
       if source_date_str:
           try:
               note.source_date = datetime.strptime(source_date_str, '%Y-%m-%d').date()
           except ValueError:
               pass

       # Parse topic tags
       topic_tags_str = request.form.get('topic_tags', '')
       if topic_tags_str:
           note.topic_tags = [tag.strip() for tag in topic_tags_str.split(',') if tag.strip()]
       else:
           note.topic_tags = None

       # Parse investor tags - automatically use source_author if provided
       if note.source_author:
           note.investor_tags = [note.source_author]
       else:
           note.investor_tags = None

       # Parse examples
       examples = request.form.get('examples', '').split('\n')
       note.examples = [ex.strip() for ex in examples if ex.strip()]

       try:
           db.session.commit()
           flash('Learning note updated!', 'success')
           return redirect(url_for('journal_enhanced.knowledge_hub', view='wisdom'))
       except Exception as e:
           db.session.rollback()
           flash(f'Error updating note: {str(e)}', 'error')

   companies = current_user.companies.order_by(Company.name).all()

   return render_template('edit_learning_note.html',
                         title="Edit Learning Note",
                         note=note,
                         companies=companies)

@journal_enhanced_bp.route('/knowledge-hub')
@login_required
def knowledge_hub():
    """Unified Knowledge Hub - combines search, curated wisdom, and research notes"""
    # Get content type filter with preference fallback
    content_type = request.args.get('type')

    if not content_type:
        # Check if user has a saved preference
        content_type = session.get('knowledge_hub_type', 'all')

    # Save the current type as preference
    session['knowledge_hub_type'] = content_type

    # Get grouping preference
    group_by = request.args.get('group_by', 'company')  # Default: group by company

    # Get search query
    search_query = request.args.get('q', '')

    # Initialize results
    wisdom_results = []
    research_results = []

    # Query LearningNote (Curated Wisdom)
    if content_type in ['all', 'wisdom']:
        wisdom_query = LearningNote.query.filter_by(user_id=current_user.id)

        # Apply wisdom-specific filters
        investor = request.args.get('investor')
        source_type = request.args.get('source_type')
        knowledge_type = request.args.get('knowledge_type')
        topic = request.args.get('topic')
        favorites_only = request.args.get('favorites_only') == '1'

        # Search filter
        if search_query:
            search_pattern = f'%{search_query}%'
            wisdom_query = wisdom_query.filter(
                db.or_(
                    LearningNote.title.ilike(search_pattern),
                    LearningNote.lesson.ilike(search_pattern),
                    LearningNote.source_author.ilike(search_pattern)
                )
            )

        # Other filters
        if investor:
            wisdom_query = wisdom_query.filter(LearningNote.investor_tags.contains([investor]))
        if source_type:
            wisdom_query = wisdom_query.filter_by(source_type=source_type)
        if knowledge_type:
            wisdom_query = wisdom_query.filter_by(knowledge_type=knowledge_type)
        if topic:
            wisdom_query = wisdom_query.filter(LearningNote.topic_tags.contains([topic]))
        if favorites_only:
            wisdom_query = wisdom_query.filter_by(is_favorite=True)

        wisdom_results = wisdom_query.order_by(
            LearningNote.importance.desc(),
            LearningNote.created_at.desc()
        ).all()

    # Query JournalEntry (Research Notes)
    if content_type in ['all', 'research']:
        research_query = JournalEntry.query.filter_by(
            user_id=current_user.id,
            is_archived=False
        )

        # Apply research-specific filters
        company_id = request.args.get('company_id', type=int)
        entry_type = request.args.get('entry_type')
        sentiment = request.args.get('sentiment')
        starred_only = request.args.get('starred_only') == '1'
        date_range = request.args.get('date_range', type=int)

        # Search filter
        if search_query:
            search_pattern = f'%{search_query}%'
            research_query = research_query.filter(
                db.or_(
                    JournalEntry.title.ilike(search_pattern),
                    JournalEntry.content.ilike(search_pattern),
                    JournalEntry.key_insight.ilike(search_pattern)
                )
            )

        # Other filters
        if company_id:
            research_query = research_query.filter_by(company_id=company_id)
        if entry_type:
            research_query = research_query.filter_by(entry_type=entry_type)
        if sentiment:
            research_query = research_query.filter_by(sentiment=sentiment)
        if starred_only:
            research_query = research_query.filter_by(is_starred=True)
        if date_range:
            cutoff_date = now_utc() - timedelta(days=date_range)
            research_query = research_query.filter(JournalEntry.created_at >= cutoff_date)

        research_results = research_query.order_by(
            JournalEntry.created_at.desc()
        ).all()

    # Build unified results list with type indicators
    unified_results = []
    for entry in research_results:
        unified_results.append({
            'type': 'research',
            'item': entry,
            'date': entry.created_at,
            'company': entry.company.name if entry.company else None,
            'company_id': entry.company_id,
            'topics': entry.tags or []
        })

    for note in wisdom_results:
        unified_results.append({
            'type': 'wisdom',
            'item': note,
            'date': note.created_at,
            'company': None,
            'company_id': None,
            'topics': note.topic_tags or []
        })

    # Sort unified results by date (most recent first)
    unified_results.sort(key=lambda x: x['date'], reverse=True)

    # Group results if requested
    grouped_results = {}
    if group_by == 'company':
        # Group by company
        for result in unified_results:
            company_name = result['company'] or 'General Knowledge'
            if company_name not in grouped_results:
                grouped_results[company_name] = []
            grouped_results[company_name].append(result)
    elif group_by == 'topic':
        # Group by topic
        for result in unified_results:
            topics = result['topics']
            if topics:
                for topic in topics:
                    topic_clean = topic.lstrip('#')
                    if topic_clean not in grouped_results:
                        grouped_results[topic_clean] = []
                    grouped_results[topic_clean].append(result)
            else:
                if 'Uncategorized' not in grouped_results:
                    grouped_results['Uncategorized'] = []
                grouped_results['Uncategorized'].append(result)
    elif group_by == 'type':
        # Group by content type
        for result in unified_results:
            type_label = 'Curated Wisdom' if result['type'] == 'wisdom' else 'Research Notes'
            if type_label not in grouped_results:
                grouped_results[type_label] = []
            grouped_results[type_label].append(result)
    elif group_by == 'date':
        # Group by date ranges
        now = now_utc()
        for result in unified_results:
            item_date = result['date']
            if item_date >= now - timedelta(days=1):
                date_label = 'Today'
            elif item_date >= now - timedelta(days=7):
                date_label = 'This Week'
            elif item_date >= now - timedelta(days=30):
                date_label = 'This Month'
            elif item_date >= now - timedelta(days=90):
                date_label = 'Last 3 Months'
            else:
                date_label = 'Older'

            if date_label not in grouped_results:
                grouped_results[date_label] = []
            grouped_results[date_label].append(result)
    else:
        # No grouping - single group
        grouped_results['All Items'] = unified_results

    # Get all unique investors for filter dropdown
    all_investors = set()
    for note in current_user.learning_notes.all():
        if note.investor_tags:
            all_investors.update(note.investor_tags)
    all_investors = sorted(list(all_investors))

    # Get all unique topics for filter dropdown
    all_topics = set()
    for note in current_user.learning_notes.all():
        if note.topic_tags:
            all_topics.update(note.topic_tags)
    all_topics = sorted(list(all_topics))

    # Get companies for filter dropdown
    companies = current_user.companies.order_by(Company.name).all()

    # Calculate stats
    all_research = current_user.journal_entries.filter_by(is_archived=False).all()
    all_wisdom = current_user.learning_notes.all()
    stats = {
        'total_items': len(all_research) + len(all_wisdom),
        'research_notes': len(all_research),
        'curated_insights': len(all_wisdom),
        'starred': sum(1 for e in all_research if e.is_starred) + sum(1 for n in all_wisdom if n.is_favorite)
    }

    return render_template('knowledge_hub.html',
                         title="Knowledge Hub",
                         content_type=content_type,
                         group_by=group_by,
                         unified_results=unified_results,
                         grouped_results=grouped_results,
                         wisdom_results=wisdom_results,
                         research_results=research_results,
                         stats=stats,
                         all_investors=all_investors,
                         all_topics=all_topics,
                         companies=companies,
                         search_query=search_query)

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
   return redirect(url_for('journal_enhanced.knowledge_hub', view='research'))

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
        return redirect(url_for('journal_enhanced.knowledge_hub', view='research'))

    except Exception as e:
        db.session.rollback()
        flash('Error deleting entry', 'error')
        return redirect(url_for('journal_enhanced.entry_detail', entry_id=entry_id))


# AI-Powered Research Journal Intelligence Routes

@journal_enhanced_bp.route('/api/entry/<int:entry_id>/analyze', methods=['POST'])
@login_required
def analyze_entry(entry_id):
    """Run AI analysis on a journal entry"""
    entry = JournalEntry.query.get_or_404(entry_id)

    # Security check
    if entry.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    try:
        # Set processing status
        entry.ai_processing_status = 'processing'
        db.session.commit()

        # Run AI analysis
        analysis_result = analyze_journal_entry(entry)

        # Store results
        entry.ai_analysis_result = analysis_result
        entry.ai_analyzed_at = now_utc()
        entry.ai_confidence_score = analysis_result.get('ai_confidence', 0.8)
        entry.ai_suggested_tags = analysis_result.get('suggested_tags', [])
        entry.ai_themes_extracted = analysis_result.get('key_themes', [])
        entry.ai_processing_status = 'completed'

        # If thesis implications found, check for contradictions
        if entry.company_id and analysis_result.get('thesis_implications'):
            contradiction_result = detect_thesis_contradictions(entry, entry.company_id)
            if contradiction_result.get('contradiction_detected'):
                entry.contradiction_flags = contradiction_result

        # Find related entries
        related_result = ai_find_related_entries(entry)
        if related_result.get('related_entries'):
            entry.related_entry_ids = [
                r['entry_id'] for r in related_result['related_entries']
                if r.get('relevance_score', 0) > 0.6  # Only store high-confidence relations
            ]

        db.session.commit()

        return jsonify({
            'success': True,
            'analysis': analysis_result,
            'has_contradictions': bool(entry.contradiction_flags),
            'related_entries_count': len(entry.related_entry_ids or [])
        })

    except Exception as e:
        # Update status on failure
        entry.ai_processing_status = 'failed'
        db.session.commit()

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@journal_enhanced_bp.route('/api/entry/<int:entry_id>/related')
@login_required
def api_get_related_entries(entry_id):
    """Get related entries for a journal entry"""
    entry = JournalEntry.query.get_or_404(entry_id)

    # Security check
    if entry.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    # Get related entries from stored IDs or run analysis
    related_entry_ids = entry.related_entry_ids or []

    if not related_entry_ids:
        # Run real-time analysis
        try:
            related_result = ai_find_related_entries(entry)
            related_entries_data = related_result.get('related_entries', [])
        except Exception as e:
            logger.error(f"Error finding related entries: {e}")
            related_entries_data = []
    else:
        # Get entries from stored IDs
        related_entries = JournalEntry.query.filter(
            JournalEntry.id.in_(related_entry_ids),
            JournalEntry.user_id == current_user.id
        ).all()

        related_entries_data = [
            {
                'entry_id': entry.id,
                'entry_title': entry.title or 'Untitled',
                'entry_type': entry.entry_type,
                'created_at': entry.created_at.strftime('%Y-%m-%d'),
                'company_name': entry.company.name if entry.company else None,
                'relevance_score': 0.8,  # Default for stored relations
                'relationship_type': 'cached'
            }
            for entry in related_entries
        ]

    return jsonify({
        'success': True,
        'related_entries': related_entries_data
    })


@journal_enhanced_bp.route('/api/entry/<int:entry_id>/contradictions')
@login_required
def get_contradictions(entry_id):
    """Get thesis contradictions for a journal entry"""
    entry = JournalEntry.query.get_or_404(entry_id)

    # Security check
    if entry.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    contradictions = entry.contradiction_flags or {}

    if not contradictions and entry.company_id:
        # Run real-time analysis
        try:
            contradictions = detect_thesis_contradictions(entry, entry.company_id)
        except Exception as e:
            logger.error(f"Error detecting contradictions: {e}")
            contradictions = {'contradiction_detected': False}

    return jsonify({
        'success': True,
        'contradictions': contradictions
    })


@journal_enhanced_bp.route('/api/entries/auto-tag', methods=['POST'])
@login_required
def auto_tag_entries():
    """Batch auto-tag recent entries that haven't been analyzed"""
    try:
        # Get recent unprocessed entries
        unprocessed_entries = JournalEntry.query.filter(
            JournalEntry.user_id == current_user.id,
            JournalEntry.ai_processing_status.is_(None)
        ).order_by(JournalEntry.created_at.desc()).limit(10).all()

        processed_count = 0
        for entry in unprocessed_entries:
            try:
                # Set processing status
                entry.ai_processing_status = 'processing'
                db.session.commit()

                # Run analysis
                analysis_result = analyze_journal_entry(entry)

                # Store AI-suggested tags
                if analysis_result.get('suggested_tags'):
                    # Merge with existing tags
                    existing_tags = set(entry.tags or [])
                    suggested_tags = set(analysis_result['suggested_tags'])
                    entry.tags = list(existing_tags.union(suggested_tags))

                entry.ai_suggested_tags = analysis_result.get('suggested_tags', [])
                entry.ai_themes_extracted = analysis_result.get('key_themes', [])
                entry.ai_processing_status = 'completed'
                entry.ai_analyzed_at = now_utc()

                processed_count += 1

            except Exception as e:
                entry.ai_processing_status = 'failed'
                logger.error(f"Failed to process entry {entry.id}: {e}")

            db.session.commit()

        return jsonify({
            'success': True,
            'processed_entries': processed_count,
            'message': f'Successfully processed {processed_count} entries'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@journal_enhanced_bp.route('/api/intelligence/dashboard')
@login_required
def intelligence_dashboard():
    """Get AI intelligence insights for the user's journal"""
    try:
        # Get statistics about AI processing
        total_entries = JournalEntry.query.filter_by(user_id=current_user.id).count()

        processed_entries = JournalEntry.query.filter(
            JournalEntry.user_id == current_user.id,
            JournalEntry.ai_processing_status == 'completed'
        ).count()

        entries_with_contradictions = JournalEntry.query.filter(
            JournalEntry.user_id == current_user.id,
            JournalEntry.contradiction_flags.isnot(None)
        ).count()

        # Get most common themes
        theme_entries = JournalEntry.query.filter(
            JournalEntry.user_id == current_user.id,
            JournalEntry.ai_themes_extracted.isnot(None)
        ).all()

        theme_counts = {}
        for entry in theme_entries:
            for theme in (entry.ai_themes_extracted or []):
                theme_counts[theme] = theme_counts.get(theme, 0) + 1

        top_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Get recent AI insights
        recent_insights = JournalEntry.query.filter(
            JournalEntry.user_id == current_user.id,
            JournalEntry.ai_analysis_result.isnot(None)
        ).order_by(JournalEntry.ai_analyzed_at.desc()).limit(5).all()

        insights_data = []
        for entry in recent_insights:
            analysis = entry.ai_analysis_result or {}
            insights_data.append({
                'entry_id': entry.id,
                'entry_title': entry.title or 'Untitled',
                'key_insights': analysis.get('key_insights', []),
                'analyzed_at': entry.ai_analyzed_at.strftime('%Y-%m-%d %H:%M') if entry.ai_analyzed_at else None
            })

        return jsonify({
            'success': True,
            'stats': {
                'total_entries': total_entries,
                'processed_entries': processed_entries,
                'processing_percentage': round((processed_entries / total_entries) * 100, 1) if total_entries > 0 else 0,
                'entries_with_contradictions': entries_with_contradictions
            },
            'top_themes': top_themes,
            'recent_insights': insights_data
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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
        # Update review information
        entry.last_reviewed = now_utc()
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
        entry.last_reviewed = now_utc()
        entry.review_count += 1
        db.session.commit()
        flash('Entry marked as reviewed', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error updating entry status', 'error')

    return redirect(url_for('journal_enhanced.entry_detail', entry_id=entry_id))
@journal_enhanced_bp.route('/api/hashtags', methods=['GET'])
@login_required
def get_hashtags():
    """Get all unique hashtags used by the current user"""
    try:
        # Get all tags from journal entries
        journal_tags = db.session.query(JournalEntry.tags).filter(
            JournalEntry.user_id == current_user.id,
            JournalEntry.tags.isnot(None)
        ).all()
        
        # Get all tags from learning notes
        learning_tags = db.session.query(LearningNote.tags).filter(
            LearningNote.user_id == current_user.id,
            LearningNote.tags.isnot(None)
        ).all()
        
        # Combine and extract unique hashtags
        all_tags = set()
        for (tags,) in journal_tags + learning_tags:
            if tags and isinstance(tags, list):
                for tag in tags:
                    if tag and tag.startswith('#'):
                        all_tags.add(tag)
        
        # Sort alphabetically
        hashtags_list = sorted(list(all_tags))
        
        return jsonify({
            'success': True,
            'hashtags': hashtags_list
        })
    except Exception as e:
        logger.error(f"Error fetching hashtags: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch hashtags'
        }), 500

@journal_enhanced_bp.route('/entry/<int:entry_id>/update-tags', methods=['POST'])
@login_required
def update_entry_tags(entry_id):
    """Update tags for a journal entry"""
    entry = JournalEntry.query.get_or_404(entry_id)
    
    # Check ownership
    if entry.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        tags = data.get('tags', [])

        # Strip # from all tags before saving (store without #)
        normalized_tags = [tag.lstrip('#') for tag in tags]

        # Update tags
        entry.tags = normalized_tags
        db.session.commit()
        
        return jsonify({
            'success': True,
            'tags': tags
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating tags: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@journal_enhanced_bp.route('/learning-notes/<int:note_id>/update-tags', methods=['POST'])
@login_required
def update_learning_note_tags(note_id):
    """Update tags for a learning note"""
    note = LearningNote.query.get_or_404(note_id)

    # Check ownership
    if note.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    try:
        data = request.get_json()
        tags = data.get('topic_tags', [])

        # Strip # from all tags before saving (store without #)
        normalized_tags = [tag.lstrip('#') for tag in tags]

        # Update topic_tags
        note.topic_tags = normalized_tags if normalized_tags else None
        db.session.commit()

        return jsonify({
            'success': True,
            'topic_tags': normalized_tags
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating learning note tags: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

