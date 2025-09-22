# app/ideas/routes.py

from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from app import db
from app.models import (IdeaPipeline, KillChecklist, KillCriterion, ResearchTemplate,
                       KillSession, KillAnswer, Company, ResearchProject, ResearchLog, JournalEntry)
from app.services.duplicate_detection import DuplicateDetectionService
from app.ideas import ideas_bp
from datetime import datetime, timedelta
from app.companies.routes import EXCHANGES # Import EXCHANGES dictionary
from app.analytics.utils import log_research_activity

@ideas_bp.route('/inbox')
@login_required
def inbox():
    """Display the user's idea inbox - ideas waiting to be evaluated"""
    # Query for ideas that are in the inbox or survived but have not been promoted
    ideas = IdeaPipeline.query.filter(
        IdeaPipeline.user_id == current_user.id,
        IdeaPipeline.status.in_(['inbox', 'survived'])
    ).order_by(IdeaPipeline.created_at.desc()).all()
    
    default_kill_checklist = KillChecklist.query.filter_by(
        user_id=current_user.id, 
        is_default=True
    ).first()
    all_kill_checklists = KillChecklist.query.filter_by(user_id=current_user.id).all()
    return render_template('inbox.html', 
                          title="Idea Inbox",
                          ideas=ideas,
                          default_kill_checklist=default_kill_checklist,
                          all_kill_checklists=all_kill_checklists,
                          now=datetime.utcnow()
                          )

@ideas_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_idea():
    """Quick capture for new ideas"""
    if request.method == 'POST':
        name = request.form.get('name')
        idea_type = request.form.get('idea_type', 'company')
        idea_purpose = request.form.get('idea_purpose', 'investment')
        ticker_symbol = request.form.get('ticker_symbol', '').upper() if request.form.get('ticker_symbol') else None
        company_id = request.form.get('company_id') if request.form.get('company_id') else None
        source = request.form.get('source')
        thesis = request.form.get('thesis_summary')
        notes = request.form.get('initial_notes')

        # Validation
        if not name:
            flash('Idea name is required', 'error')
            return redirect(url_for('ideas.add_idea'))

        if not source:
            flash('Source is required - please specify where this idea came from', 'error')
            return redirect(url_for('ideas.add_idea'))

        # Validate company requirement for investment companies
        if idea_purpose == 'investment' and idea_type == 'company' and not company_id:
            flash('Company selection is required for company investment ideas', 'error')
            return redirect(url_for('ideas.add_idea'))

        # Check for existing research projects for this company (Intelligent Duplication Prevention)
        if company_id:
            # Check for active research project
            active_project = ResearchProject.query.filter_by(
                user_id=current_user.id,
                company_id=company_id,
                status='active'
            ).first()

            if active_project:
                flash(f'You already have an active research project for this company. Redirecting to project dashboard.', 'info')
                return redirect(url_for('research_workflow.project_dashboard', project_id=active_project.id))

            # Check for completed research project
            completed_project = ResearchProject.query.filter_by(
                user_id=current_user.id,
                company_id=company_id,
                status='completed'
            ).first()

            if completed_project:
                flash(f'You already have completed research for this company. Redirecting to project summary.', 'info')
                return redirect(url_for('research_workflow.project_summary', project_id=completed_project.id))

        # Enhanced duplicate detection
        detector = DuplicateDetectionService(current_user.id)
        duplicate_check = detector.check_idea_duplicates(name, ticker_symbol)

        if duplicate_check['is_duplicate']:
            # Handle blocking duplicates
            for match in duplicate_check['exact_matches']:
                flash(match['message'], 'error')
            for match in duplicate_check['similar_matches']:
                if match.get('similarity', 0) > 0.9:  # Very similar names should block
                    flash(match['message'], 'error')
            return redirect(url_for('ideas.add_idea'))

        # Show warnings and suggestions but allow creation
        for match in duplicate_check['similar_matches']:
            if match.get('similarity', 0) <= 0.9:  # Show warning but don't block
                flash(f"Warning: {match['message']}", 'warning')

        for suggestion in duplicate_check['suggestions']:
            if suggestion['type'] == 'killed_idea_exists':
                flash(f"Note: {suggestion['message']}", 'info')
            elif suggestion['type'] == 'promote_existing_company':
                flash(f"Suggestion: {suggestion['message']}", 'info')

        new_idea = IdeaPipeline(
            author=current_user, name=name, idea_type=idea_type, idea_purpose=idea_purpose,
            ticker_symbol=ticker_symbol, company_id=company_id, source=source, thesis_summary=thesis,
            initial_notes=notes, status='inbox'
        )

        try:
            db.session.add(new_idea)
            db.session.commit()
            log_research_activity(
                current_user.id,
                'idea_captured',
                idea_id=new_idea.id,
                details={'source': source, 'type': idea_type}
            )
            flash(f'"{name}" added to your idea inbox!', 'success')
            return redirect(url_for('ideas.inbox'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding idea: {str(e)}', 'error')

    return render_template('add_idea.html', title="Quick Capture")

# In app/ideas/routes.py

@ideas_bp.route('/<int:idea_id>/kill', methods=['GET', 'POST'])
@login_required
def kill_room(idea_id):
    """The kill room - evaluate an idea against kill criteria"""
    idea = IdeaPipeline.query.get_or_404(idea_id)
    checklist_id = request.args.get('checklist_id', type=int) # Get checklist_id from URL

    if idea.user_id != current_user.id:
        flash('You do not have access to this idea', 'error')
        return redirect(url_for('ideas.inbox'))

    # Logic to find or create a kill session
    kill_session = KillSession.query.filter_by(
        user_id=current_user.id, idea_id=idea.id, outcome=None
    ).first()

    if not kill_session:
        kill_checklist = None
        if checklist_id:
            # Use the checklist passed from the URL
            kill_checklist = KillChecklist.query.filter_by(id=checklist_id, user_id=current_user.id).first()
        else:
            # Fallback to the default checklist if no ID is passed
            kill_checklist = KillChecklist.query.filter_by(user_id=current_user.id, is_default=True).first()

        if not kill_checklist:
            flash('Please create a kill checklist first or set one as default.', 'warning')
            return redirect(url_for('ideas.manage_kill_checklists'))
            
        kill_session = KillSession(user_id=current_user.id, idea=idea, checklist=kill_checklist)
        db.session.add(kill_session)
        idea.status = 'killing'
        db.session.commit()

    # The rest of your kill_room function remains the same...
    criteria = kill_session.checklist.criteria.order_by(KillCriterion.order).all()
    existing_answers = {ans.criterion_id: ans for ans in kill_session.answers.all()}
    
    current_criterion = None
    current_index = 0
    for i, criterion in enumerate(criteria):
        if criterion.id not in existing_answers:
            current_criterion = criterion
            current_index = i
            break

    if request.method == 'POST' and current_criterion:
        passed = request.form.get('passed') == 'true'
        notes = request.form.get('notes', '')
        answer = KillAnswer(session=kill_session, criterion=current_criterion, passed=passed, notes=notes)
        db.session.add(answer)
        current_criterion.times_evaluated += 1
        
        if not passed:
            current_criterion.times_failed += 1
            idea.status = 'killed'
            idea.kill_reason = current_criterion.question
            idea.failed_criterion = current_criterion
            idea.killed_at = datetime.utcnow()
            kill_session.outcome = 'killed'
            kill_session.completed_at = datetime.utcnow()
            kill_session.checklist.total_ideas_evaluated += 1
            kill_session.checklist.total_ideas_killed += 1
            db.session.commit()
            log_research_activity(
            current_user.id,
            'idea_killed',
            idea_id=idea.id,
            details={'reason': current_criterion.question}
        )
            flash(f'"{idea.name}" has been killed. Reason: {current_criterion.question}', 'info')
            return redirect(url_for('ideas.graveyard'))

        db.session.commit()

        next_criterion_found = False
        for i, criterion in enumerate(criteria):
            if criterion.id not in {ans.criterion_id for ans in kill_session.answers.all()}:
                return redirect(url_for('ideas.kill_room', idea_id=idea.id, checklist_id=kill_session.checklist.id))
        
        # If no next criterion is found, the idea survived
        idea.status = 'survived'
        idea.promoted_at = datetime.utcnow()
        kill_session.outcome = 'survived'
        kill_session.completed_at = datetime.utcnow()
        kill_session.checklist.total_ideas_evaluated += 1
        db.session.commit()
        
        log_research_activity(
            current_user.id,
            'idea_promoted',
            idea_id=idea.id
        )
        flash(f'🎉 "{idea.name}" survived the kill checklist! Ready for promotion.', 'success')
        return redirect(url_for('ideas.promote_idea', idea_id=idea.id))


    progress_percent = (len(existing_answers) / len(criteria)) * 100 if criteria else 0
    return render_template('kill_room.html', title=f"Kill Room: {idea.name}", idea=idea,
                           session=kill_session, current_criterion=current_criterion,
                           current_index=current_index, total_criteria=len(criteria),
                           progress_percent=progress_percent, existing_answers=existing_answers)

@ideas_bp.route('/graveyard')
@login_required
def graveyard():
    killed_ideas = current_user.idea_pipeline.filter_by(status='killed').order_by(IdeaPipeline.killed_at.desc()).all()
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_kill_count = sum(1 for idea in killed_ideas if idea.killed_at and idea.killed_at > thirty_days_ago)
    kill_reasons = {}
    for idea in killed_ideas:
        reason = idea.kill_reason or "Unknown"
        if reason not in kill_reasons:
            kill_reasons[reason] = []
        kill_reasons[reason].append(idea)
    return render_template('graveyard.html', title="Idea Graveyard", killed_ideas=killed_ideas,
                           kill_reasons=kill_reasons, recent_kill_count=recent_kill_count)

@ideas_bp.route('/kill-checklists')
@login_required
def manage_kill_checklists():
    checklists = current_user.kill_checklists.all()
    return render_template('manage_kill_checklists.html', title="Kill Checklists", checklists=checklists)

@ideas_bp.route('/kill-checklists/new', methods=['GET', 'POST'])
@login_required
def create_kill_checklist():
    if request.method == 'POST':
        name = request.form.get('name')
        if not name:
            flash('Checklist name is required', 'error')
            return redirect(url_for('ideas.create_kill_checklist'))
        
        is_default = request.form.get('is_default') == 'true'
        if is_default:
            KillChecklist.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})
        
        checklist = KillChecklist(
            author=current_user, name=name, description=request.form.get('description'), is_default=is_default
        )
        db.session.add(checklist)
        db.session.flush()
        
        criteria_questions = request.form.getlist('criterion_question[]')
        criteria_reasons = request.form.getlist('criterion_reason[]')
        for i, question in enumerate(criteria_questions):
            if question.strip():
                criterion = KillCriterion(
                    kill_checklist=checklist, question=question.strip(),
                    failure_reason=criteria_reasons[i] if i < len(criteria_reasons) else '', order=i
                )
                db.session.add(criterion)
        
        db.session.commit()
        flash(f'Kill checklist "{name}" created!', 'success')
        return redirect(url_for('ideas.manage_kill_checklists'))
    
    return render_template('create_kill_checklist.html', title="Create Kill Checklist")

@ideas_bp.route('/kill-checklists/<int:checklist_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_kill_checklist(checklist_id):
    checklist = KillChecklist.query.get_or_404(checklist_id)
    if checklist.user_id != current_user.id:
        flash('You do not have permission to edit this checklist.', 'error')
        return redirect(url_for('ideas.manage_kill_checklists'))
    
    if request.method == 'POST':
        checklist.name = request.form.get('name')
        checklist.description = request.form.get('description')
        is_default = request.form.get('is_default') == 'true'
        if is_default and not checklist.is_default:
            KillChecklist.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})
        checklist.is_default = is_default
        
        criteria_ids = request.form.getlist('criterion_id[]')
        criteria_questions = request.form.getlist('criterion_question[]')
        criteria_reasons = request.form.getlist('criterion_reason[]')
        
        existing_criterion_ids = {c.id for c in checklist.criteria}
        submitted_criterion_ids = {int(id) for id in criteria_ids if id}
        ids_to_delete = existing_criterion_ids - submitted_criterion_ids
        if ids_to_delete:
            KillCriterion.query.filter(KillCriterion.id.in_(ids_to_delete)).delete(synchronize_session=False)
        
        for i, question in enumerate(criteria_questions):
            if question.strip():
                criterion_id = criteria_ids[i] if i < len(criteria_ids) and criteria_ids[i] else None
                if criterion_id:
                    criterion = KillCriterion.query.get(criterion_id)
                    criterion.question = question.strip()
                    criterion.failure_reason = criteria_reasons[i] if i < len(criteria_reasons) else ''
                    criterion.order = i
                else:
                    criterion = KillCriterion(
                        kill_checklist=checklist, question=question.strip(),
                        failure_reason=criteria_reasons[i] if i < len(criteria_reasons) else '', order=i
                    )
                    db.session.add(criterion)
        
        db.session.commit()
        flash(f'Kill checklist "{checklist.name}" updated!', 'success')
        return redirect(url_for('ideas.manage_kill_checklists'))
    
    return render_template('edit_kill_checklist.html', title="Edit Kill Checklist", checklist=checklist)

@ideas_bp.route('/kill-checklists/<int:checklist_id>/delete', methods=['POST'])
@login_required
def delete_kill_checklist(checklist_id):
    checklist = KillChecklist.query.get_or_404(checklist_id)
    if checklist.user_id != current_user.id:
        flash('You do not have permission to delete this checklist.', 'error')
        return redirect(url_for('ideas.manage_kill_checklists'))
    
    db.session.delete(checklist)
    db.session.commit()
    flash(f'Kill checklist "{checklist.name}" has been deleted.', 'success')
    return redirect(url_for('ideas.manage_kill_checklists'))

@ideas_bp.route('/<int:idea_id>/promote', methods=['GET', 'POST'])
@login_required
def promote_idea(idea_id):
    idea = IdeaPipeline.query.get_or_404(idea_id)
    if idea.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('ideas.inbox'))
    
    # Validate idea type requirements - only investment company ideas need ticker symbols
    if idea.idea_purpose == 'investment' and idea.idea_type == 'company' and not idea.ticker_symbol:
        flash(f'Cannot promote "{idea.name}". Investment company ideas require a ticker symbol.', 'error')
        return redirect(url_for('ideas.inbox'))
    
    if request.method == 'POST':
        promotion_action = request.form.get('action')
        
        if promotion_action == 'create_company' and idea.idea_type == 'company':
            # Check if company with ticker already exists
            if idea.ticker_symbol:
                existing_company = Company.query.filter_by(ticker_symbol=idea.ticker_symbol).first()
                if existing_company:
                    flash(f'Company with ticker {idea.ticker_symbol} already exists: {existing_company.name}', 'error')
                    return redirect(request.url)

            # Create company and redirect to research template selection
            company = Company(
                name=idea.name, ticker_symbol=idea.ticker_symbol,
                creator=current_user, summary=idea.thesis_summary
            )
            db.session.add(company)
            db.session.flush()
            idea.promoted_to_company = company
            idea.status = 'promoted'
            idea.promoted_at = datetime.utcnow()
            db.session.commit()
            flash(f'"{idea.name}" promoted to your companies list!', 'success')
            return redirect(url_for('research_workflow.intelligent_routing', company_id=company.id, source='idea_promotion'))
            
        elif promotion_action == 'create_research_project':
            # Create research project directly based on idea type
            template_id = request.form.get('template_id', type=int)
            if not template_id:
                flash('Please select a research template', 'error')
                return redirect(request.url)
            
            # Verify template ownership
            template = ResearchTemplate.query.get_or_404(template_id)
            if template.user_id != current_user.id:
                flash('Access denied', 'error')
                return redirect(url_for('ideas.inbox'))

            # For company ideas, ensure promoted_to_company is set correctly
            if idea.idea_type == 'company' and idea.company and not idea.promoted_to_company:
                idea.promoted_to_company = idea.company

            # ENFORCE CONSTRAINT: ONE RESEARCH PROJECT PER COMPANY
            company_for_constraint_check = idea.promoted_to_company or idea.company
            if idea.idea_type == 'company' and company_for_constraint_check:
                existing_project = ResearchProject.query.filter_by(
                    user_id=current_user.id,
                    company_id=company_for_constraint_check.id
                ).filter(
                    ResearchProject.status.in_(['active', 'paused'])
                ).first()

                if existing_project:
                    flash(f'You already have a research project for {company_for_constraint_check.name}. Only one project per company is allowed.', 'error')
                    return redirect(url_for('research_workflow.project_dashboard', project_id=existing_project.id))

            # Create research project
            project = ResearchProject(
                researcher=current_user,
                template=template,
                research_subject_type=idea.idea_type,
                research_subject_name=idea.name,
                company_id=company_for_constraint_check.id if (idea.idea_type == 'company' and company_for_constraint_check) else None,
                project_name=f"{idea.name} - {template.name}",
                status='active',
                idea=idea,
                investment_thesis=idea.thesis_summary
            )
            
            # Update template usage count
            template.times_used += 1
            
            try:
                db.session.add(project)
                idea.status = 'promoted'
                idea.promoted_at = datetime.utcnow()
                db.session.commit()
                
                from app.analytics.utils import log_research_activity
                log_research_activity(
                    current_user.id,
                    'research_started',
                    company_id=project.company_id if project.company else None,
                    project_id=project.id
                )
                
                flash(f'Research project started for {idea.name}!', 'success')
                return redirect(url_for('research_workflow.project_dashboard', project_id=project.id))
            except Exception as e:
                db.session.rollback()
                flash(f'Error starting research project: {str(e)}', 'error')
                return redirect(url_for('ideas.inbox'))
    
    # Get available templates for the GET request
    templates = current_user.research_templates.filter_by(is_active=True).order_by(ResearchTemplate.times_used.desc()).all()
    
    return render_template('promote_idea.html', 
                          title=f"Promote {idea.idea_type.title()}: {idea.name}", 
                          idea=idea, 
                          templates=templates,
                          datetime=datetime)

@ideas_bp.route('/<int:idea_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_idea(idea_id):
    idea = IdeaPipeline.query.get_or_404(idea_id)
    if idea.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('ideas.inbox'))
    
    if request.method == 'POST':
        idea.name = request.form.get('name', idea.name)
        idea.idea_type = request.form.get('idea_type', idea.idea_type)
        idea.idea_purpose = request.form.get('idea_purpose', idea.idea_purpose)
        base_ticker = request.form.get('base_ticker', '').upper()
        exchange_suffix = request.form.get('exchange_suffix', '')
        new_ticker = f"{base_ticker}{exchange_suffix}" if base_ticker else None

        # Check if changing ticker to one that already exists
        if new_ticker and new_ticker != idea.ticker_symbol:
            # Check existing companies
            existing_company = Company.query.filter_by(
                ticker_symbol=new_ticker,
                user_id=current_user.id
            ).first()
            if existing_company:
                flash(f'You already have a company with ticker {new_ticker}: {existing_company.name}. Cannot change to this ticker.', 'error')
                return redirect(url_for('ideas.edit_idea', idea_id=idea.id))

            # Check existing ideas (excluding current idea)
            existing_idea = IdeaPipeline.query.filter(
                IdeaPipeline.ticker_symbol == new_ticker,
                IdeaPipeline.user_id == current_user.id,
                IdeaPipeline.id != idea.id
            ).first()
            if existing_idea:
                flash(f'You already have an idea with ticker {new_ticker}: {existing_idea.name} (Status: {existing_idea.status}). Cannot change to this ticker.', 'error')
                return redirect(url_for('ideas.edit_idea', idea_id=idea.id))

        idea.ticker_symbol = new_ticker
        idea.source = request.form.get('source')
        idea.thesis_summary = request.form.get('thesis_summary')
        idea.initial_notes = request.form.get('initial_notes')

        try:
            db.session.commit()
            flash('Idea updated successfully', 'success')
            return redirect(url_for('ideas.inbox'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating idea: {str(e)}', 'error')
            
    base_ticker, exchange_suffix = '', ''
    if idea.ticker_symbol:
        if '.' in idea.ticker_symbol:
            parts = idea.ticker_symbol.rsplit('.', 1)
            base_ticker = parts[0]
            exchange_suffix = '.' + parts[1]
        else:
            base_ticker = idea.ticker_symbol
            
    return render_template('edit_idea.html', title="Edit Idea", idea=idea,
                           exchanges=EXCHANGES, base_ticker=base_ticker, exchange_suffix=exchange_suffix)

@ideas_bp.route('/<int:idea_id>/delete', methods=['POST'])
@login_required
def delete_idea(idea_id):
    idea = IdeaPipeline.query.get_or_404(idea_id)
    if idea.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('ideas.inbox'))

    try:
        # Delete research logs that reference this idea
        ResearchLog.query.filter_by(idea_id=idea_id).delete()

        # Delete journal entries that reference this idea
        JournalEntry.query.filter_by(idea_id=idea_id).delete()

        # Update research projects to remove idea reference (don't delete projects)
        ResearchProject.query.filter_by(idea_id=idea_id).update({'idea_id': None})

        # Now delete the idea (KillSession will cascade delete automatically)
        db.session.delete(idea)
        db.session.commit()
        flash(f'"{idea.name}" deleted permanently', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting idea: {str(e)}', 'error')

    return redirect(url_for('ideas.inbox'))

@ideas_bp.route('/<int:idea_id>/resurrect', methods=['POST'])
@login_required
def resurrect_idea(idea_id):
    idea = IdeaPipeline.query.get_or_404(idea_id)
    if idea.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    idea.status = 'inbox'
    idea.kill_reason = None
    idea.failed_criterion_id = None
    idea.killed_at = None
    
    try:
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@ideas_bp.route('/<int:idea_id>/mark_someday', methods=['GET'])
@login_required
def mark_someday(idea_id):
    idea = IdeaPipeline.query.get_or_404(idea_id)
    if idea.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('ideas.inbox'))
    
    idea.status = 'someday'
    idea.last_reviewed_at = datetime.utcnow()
    
    try:
        db.session.commit()
        flash(f'"{idea.name}" moved to Someday/Maybe', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating idea: {str(e)}', 'error')
    
    return redirect(url_for('ideas.inbox'))

@ideas_bp.route('/kill-checklists/<int:checklist_id>/set-default', methods=['POST'])
@login_required
def set_default_checklist(checklist_id):
    checklist = KillChecklist.query.get_or_404(checklist_id)
    if checklist.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('ideas.manage_kill_checklists'))
    
    KillChecklist.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})
    checklist.is_default = True
    
    try:
        db.session.commit()
        flash(f'"{checklist.name}" set as default kill checklist', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating checklist: {str(e)}', 'error')
    
    return redirect(url_for('ideas.manage_kill_checklists'))

@ideas_bp.route('/<int:idea_id>/details')
@login_required
def idea_details(idea_id):
    idea = IdeaPipeline.query.get_or_404(idea_id)
    if idea.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('ideas.inbox'))
    return redirect(url_for('ideas.edit_idea', idea_id=idea.id))

@ideas_bp.route('/api/sources/search')
@login_required
def search_sources():
    """AJAX endpoint to search for existing idea sources"""
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify([])

    # Search for sources that contain the query (case insensitive)
    # Get distinct sources from user's ideas, ordered by frequency
    sources = db.session.query(IdeaPipeline.source, db.func.count(IdeaPipeline.source).label('count')) \
        .filter(IdeaPipeline.user_id == current_user.id) \
        .filter(IdeaPipeline.source.ilike(f'%{query}%')) \
        .filter(IdeaPipeline.source.isnot(None)) \
        .group_by(IdeaPipeline.source) \
        .order_by(db.func.count(IdeaPipeline.source).desc()) \
        .limit(10) \
        .all()

    # Return list of source names
    result = [{'source': source[0], 'count': source[1]} for source in sources]
    return jsonify(result)