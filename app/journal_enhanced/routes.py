# Investment Checklist Platform
# Copyright (C) 2024-2026 Kiran Mathews
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

from flask import render_template, request, redirect, url_for, flash, jsonify, send_from_directory, abort, session
from flask_login import current_user, login_required
from app import db
from app.models import (JournalEntry, ThesisEvolution, LearningNote,
                       JournalTemplate, JournalAttachment, Company,
                       ResearchProject, MistakeLog)
from app.journal_enhanced import journal_enhanced_bp
from app.journal_enhanced.utils import (extract_tags_from_content, get_related_entries,
                                       update_thesis_version, create_default_templates)
from app.utils.time_utils import now_utc, parse_date_to_date_object
from app.utils.response_utils import json_success, json_error, json_unauthorized
from app.utils.blocknote_utils import blocknote_to_text
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
            return_url = request.form.get('return_url') or url_for('journal_enhanced.knowledge_hub', view='research')
            return redirect(return_url)
            
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
    preset_company = None
    if company_id:
        preset_company = Company.query.filter_by(id=company_id, user_id=current_user.id).first()

    return_url = request.args.get('return_url')

    return render_template('new_entry.html',
                          title="New Journal Entry",
                          templates=templates,
                          companies=companies,
                          selected_template=selected_template,
                          preset_company_id=company_id,
                          preset_company=preset_company,
                          return_url=return_url)

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
       entry.entry_type = request.form.get('entry_type', entry.entry_type)
       entry.key_insight = request.form.get('key_insight')
       entry.sentiment = request.form.get('sentiment')
       entry.conviction_level = request.form.get('conviction', type=int)
       entry.source = request.form.get('source')

       # Update company association
       company_id = request.form.get('company_id')
       entry.company_id = int(company_id) if company_id else None

       # Update tags
       entry.tags = extract_tags_from_content(entry.content)

       # Update action items and questions
       action_items = request.form.get('action_items', '').split('\n')
       entry.action_items = [item.strip() for item in action_items if item.strip()]

       questions = request.form.get('questions_raised', '').split('\n')
       entry.questions_raised = [q.strip() for q in questions if q.strip()]

       entry.updated_at = now_utc()

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
       return json_unauthorized('Access denied')
   
   entry.is_starred = not entry.is_starred
   
   try:
       db.session.commit()
       return jsonify({'starred': entry.is_starred})
   except Exception as e:
       db.session.rollback()
       return json_error(str(e), status_code=500)

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
       source_date_str = request.form.get('source_date')
       source_date = parse_date_to_date_object(source_date_str) if source_date_str else None

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

@journal_enhanced_bp.route('/learning-notes/<int:note_id>/toggle-favorite', methods=['POST'])
@login_required
def toggle_favorite_note(note_id):
   """Toggle favorite status of a learning note"""
   note = LearningNote.query.get_or_404(note_id)

   if note.user_id != current_user.id:
       return json_unauthorized('Access denied')

   note.is_favorite = not note.is_favorite

   try:
       db.session.commit()
       return json_success(data={'is_favorite': note.is_favorite})
   except Exception as e:
       db.session.rollback()
       return json_error(str(e), status_code=500)

@journal_enhanced_bp.route('/learning-notes/<int:note_id>/delete', methods=['POST'])
@login_required
def delete_learning_note(note_id):
   """Delete a learning note"""
   note = LearningNote.query.get_or_404(note_id)

   if note.user_id != current_user.id:
       return json_unauthorized('Access denied')

   try:
       db.session.delete(note)
       db.session.commit()
       return json_success()
   except Exception as e:
       db.session.rollback()
       return json_error(str(e), status_code=500)

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
           note.source_date = parse_date_to_date_object(source_date_str)

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
    """Command Center - unified knowledge hub for research, wisdom, and mistakes"""
    # Get filter params
    content_type = request.args.get('type', session.get('knowledge_hub_type', 'all'))
    session['knowledge_hub_type'] = content_type
    search_query = request.args.get('q', '')
    company_filter = request.args.get('company_id', type=int)
    tag_filter = request.args.get('tag')
    starred_only = request.args.get('starred') == '1'
    sort_by = request.args.get('sort', 'date')

    # Build unified results
    unified_results = []

    # --- Query Research Notes (JournalEntry) ---
    if content_type in ['all', 'research']:
        research_query = JournalEntry.query.filter_by(
            user_id=current_user.id, is_archived=False
        )
        if search_query:
            pattern = f'%{search_query}%'
            research_query = research_query.filter(db.or_(
                JournalEntry.title.ilike(pattern),
                JournalEntry.content.ilike(pattern),
                JournalEntry.key_insight.ilike(pattern)
            ))
        if company_filter:
            research_query = research_query.filter_by(company_id=company_filter)
        if starred_only:
            research_query = research_query.filter_by(is_starred=True)
        for entry in research_query.order_by(JournalEntry.created_at.desc()).all():
            # Tag filtering in Python for PostgreSQL JSON compat
            if tag_filter and (not entry.tags or tag_filter not in entry.tags):
                continue
            unified_results.append({
                'type': 'research', 'item': entry, 'date': entry.created_at,
                'title': entry.title or 'Untitled',
                'preview': entry.key_insight or blocknote_to_text(entry.content)[:150],
                'company': entry.company.name if entry.company else None,
                'company_id': entry.company_id,
                'tags': entry.tags or [],
                'starred': entry.is_starred,
            })

    # --- Query Curated Wisdom (LearningNote) ---
    if content_type in ['all', 'wisdom']:
        wisdom_query = LearningNote.query.filter_by(user_id=current_user.id)
        if search_query:
            pattern = f'%{search_query}%'
            wisdom_query = wisdom_query.filter(db.or_(
                LearningNote.title.ilike(pattern),
                LearningNote.lesson.ilike(pattern),
                LearningNote.source_author.ilike(pattern)
            ))
        if company_filter:
            wisdom_query = wisdom_query.filter_by(company_id=company_filter)
        if starred_only:
            wisdom_query = wisdom_query.filter_by(is_favorite=True)
        for note in wisdom_query.order_by(LearningNote.created_at.desc()).all():
            if tag_filter:
                all_note_tags = (note.topic_tags or []) + (note.tags or [])
                if tag_filter not in all_note_tags:
                    continue
            unified_results.append({
                'type': 'wisdom', 'item': note, 'date': note.created_at,
                'title': note.title,
                'preview': blocknote_to_text(note.lesson)[:150] if note.lesson else '',
                'company': note.company.name if note.company else None,
                'company_id': note.company_id,
                'tags': note.topic_tags or note.tags or [],
                'starred': note.is_favorite,
                'author': note.source_author,
            })

    # --- Query Mistakes (MistakeLog) ---
    if content_type in ['all', 'mistake']:
        mistake_query = MistakeLog.query.filter_by(user_id=current_user.id)
        if search_query:
            pattern = f'%{search_query}%'
            mistake_query = mistake_query.filter(db.or_(
                MistakeLog.title.ilike(pattern),
                MistakeLog.description.ilike(pattern),
                MistakeLog.lesson_learned.ilike(pattern)
            ))
        if company_filter:
            mistake_query = mistake_query.filter_by(company_id=company_filter)
        for mistake in mistake_query.order_by(MistakeLog.created_at.desc()).all():
            unified_results.append({
                'type': 'mistake', 'item': mistake, 'date': mistake.created_at,
                'title': mistake.title,
                'preview': blocknote_to_text(mistake.lesson_learned or mistake.description)[:150],
                'company': mistake.company.name if mistake.company else None,
                'company_id': mistake.company_id,
                'tags': [],
                'starred': False,
                'severity': mistake.severity,
            })

    # Sort
    if sort_by == 'title':
        unified_results.sort(key=lambda x: (x['title'] or '').lower())
    elif sort_by == 'type':
        unified_results.sort(key=lambda x: x['type'])
    else:
        unified_results.sort(key=lambda x: x['date'], reverse=True)

    # Group by date (always date-grouped in Command Center)
    now = now_utc().replace(tzinfo=None)
    date_order = ['This Week', 'This Month', 'Last 3 Months', 'Older']
    grouped_results = {}
    for result in unified_results:
        item_date = result['date'].replace(tzinfo=None) if result['date'].tzinfo else result['date']
        diff = (now - item_date).days
        if diff < 7:
            label = 'This Week'
        elif diff < 30:
            label = 'This Month'
        elif diff < 90:
            label = 'Last 3 Months'
        else:
            label = 'Older'
        if label not in grouped_results:
            grouped_results[label] = []
        grouped_results[label].append(result)

    # Preserve date order
    ordered_groups = [(k, grouped_results[k]) for k in date_order if k in grouped_results]

    # Collect filter dropdown data
    companies = current_user.companies.order_by(Company.name).all()
    all_tags = set()
    for entry in current_user.journal_entries.filter(JournalEntry.tags.isnot(None)):
        if entry.tags:
            all_tags.update(entry.tags)
    for note in current_user.learning_notes.filter(LearningNote.topic_tags.isnot(None)):
        if note.topic_tags:
            all_tags.update(note.topic_tags)
    all_tags = sorted(all_tags)

    # Type counts for tabs
    all_research_count = current_user.journal_entries.filter_by(is_archived=False).count()
    all_wisdom_count = current_user.learning_notes.count()
    all_mistake_count = MistakeLog.query.filter_by(user_id=current_user.id).count()
    total_count = all_research_count + all_wisdom_count + all_mistake_count

    type_counts = {
        'all': total_count,
        'research': all_research_count,
        'wisdom': all_wisdom_count,
        'mistake': all_mistake_count,
    }

    return render_template('knowledge_hub.html',
                         title="Knowledge Hub",
                         content_type=content_type,
                         unified_results=unified_results,
                         grouped_results=ordered_groups,
                         type_counts=type_counts,
                         companies=companies,
                         all_tags=all_tags,
                         search_query=search_query,
                         company_filter=company_filter,
                         tag_filter=tag_filter,
                         starred_only=starred_only,
                         sort_by=sort_by)

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
        return json_unauthorized('Access denied')

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
        return json_unauthorized('Access denied')

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
        return json_unauthorized('Access denied')

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
        return json_unauthorized('Unauthorized')
    
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
        return json_unauthorized('Unauthorized')

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

