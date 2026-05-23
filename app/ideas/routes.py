# app/ideas/routes.py

import copy
from flask import render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_login import current_user, login_required
from app import db
from app.models import (IdeaPipeline, KillChecklist, KillCriterion, ResearchTemplate,
                       KillSession, KillAnswer, Company, ResearchProject, ResearchLog, JournalEntry,
                       KillChecklistSuggestion, MistakeLog, SectorAnalysis)
from app.utils.response_utils import json_success, json_error, json_unauthorized
from app.utils.decorators import require_feature
from app.services.duplicate_detection import DuplicateDetectionService
from app.services.kill_checklist_analytics import KillChecklistAnalytics, SuggestionEngine
from app.ideas import ideas_bp
from app.sectors.routes import initialize_default_sections
from app.companies.routes import EXCHANGES # Import EXCHANGES dictionary
from app.analytics.utils import log_research_activity
from app.research_workflow.template_routes import ensure_default_template
from app.utils.time_utils import now_utc, ensure_timezone_aware
from sqlalchemy import or_, and_
import json
import os
import yaml
from sqlalchemy import func


def ensure_default_checklist(user):
    """Create a default kill checklist from YAML config if the user has none.

    Returns:
        tuple: (checklist, is_new) — is_new=True if just created, so caller can redirect to edit.
    """
    checklist = KillChecklist.query.filter_by(user_id=user.id).first()
    if checklist:
        return checklist, False

    yaml_path = os.path.join(os.path.dirname(__file__), 'defaults', 'kill_checklist.yaml')
    with open(yaml_path, 'r') as f:
        defaults = yaml.safe_load(f)

    checklist = KillChecklist(
        user_id=user.id,
        name=defaults['name'],
        description=defaults['description'],
        is_default=True,
    )
    db.session.add(checklist)
    db.session.flush()

    for i, item in enumerate(defaults['criteria']):
        criterion = KillCriterion(
            kill_checklist_id=checklist.id,
            question=item['question'],
            help_text=item.get('help_text', ''),
            failure_reason=item.get('failure_reason', ''),
            order=i,
        )
        db.session.add(criterion)

    db.session.commit()
    return checklist, True


@ideas_bp.route('/inbox')
@login_required
def inbox():
    """Display the user's idea inbox - ideas waiting to be evaluated"""
    # Query for ideas that are in the inbox, being evaluated (killing), survived,
    # or promoted but without a research project (orphaned)
    ideas = IdeaPipeline.query.filter(
        IdeaPipeline.user_id == current_user.id,
        or_(
            IdeaPipeline.status.in_(['inbox', 'killing', 'survived']),
            # Include promoted ideas that don't have an associated research project
            and_(
                IdeaPipeline.status == 'promoted',
                IdeaPipeline.research_project == None
            )
        )
    ).order_by(IdeaPipeline.created_at.desc()).all()

    # Ensure the user has a default kill checklist (auto-create from YAML if needed)
    default_kill_checklist, is_new_checklist = ensure_default_checklist(current_user)
    if is_new_checklist:
        flash('We created a default evaluation checklist for you. Review and customize it, then come back to evaluate ideas.', 'info')
        return redirect(url_for('ideas.edit_kill_checklist', checklist_id=default_kill_checklist.id))
    all_kill_checklists = KillChecklist.query.filter_by(user_id=current_user.id).all()

    # Calculate days since oldest idea and per-idea ages
    current_time = now_utc()
    days_since_oldest = None
    idea_ages = {}
    for idea in ideas:
        if idea.created_at:
            aware_dt = ensure_timezone_aware(idea.created_at)
            age = (current_time - aware_dt).days
            idea_ages[idea.id] = age
        else:
            idea_ages[idea.id] = 0
    if ideas:
        days_since_oldest = max(idea_ages.values())

    # State counts for metrics strip and filter buttons
    waiting_count = sum(1 for i in ideas if i.status == 'inbox')
    killing_count = sum(1 for i in ideas if i.status == 'killing')
    ready_count = sum(1 for i in ideas if i.status in ('survived', 'promoted'))

    # Serialize ideas for Tabulator (pre-compute actions to avoid complex JS logic)
    ideas_data = []
    for idea in ideas:
        # Determine display state
        if idea.status == 'killing':
            display_state = 'killing'
        elif idea.status in ('survived', 'promoted'):
            display_state = 'ready'
        else:
            display_state = 'waiting'

        # Pre-compute primary action
        action = {}
        if idea.status == 'killing':
            action = {'type': 'evaluate', 'url': url_for('ideas.kill_room', idea_id=idea.id),
                      'label': 'Continue', 'icon': 'bi-arrow-clockwise'}
        elif idea.status == 'promoted':
            action = {'type': 'promote', 'url': url_for('ideas.promote_idea', idea_id=idea.id),
                      'label': 'Template', 'icon': 'bi-rocket-takeoff'}
        elif idea.status == 'survived' or idea.idea_purpose in ('learning', 'research'):
            lbl, icon = 'Start', 'bi-search'
            if idea.idea_purpose == 'learning':
                icon = 'bi-book'
            elif idea.idea_purpose == 'research':
                icon = 'bi-search'
            elif idea.idea_type == 'company':
                lbl, icon = 'Promote', 'bi-arrow-up-circle'
            elif idea.idea_type == 'sector':
                lbl, icon = 'Notebook', 'bi-journal-plus'
            action = {'type': 'promote', 'url': url_for('ideas.promote_idea', idea_id=idea.id),
                      'label': lbl, 'icon': icon}
        elif idea.idea_type == 'sector':
            action = {'type': 'promote', 'url': url_for('ideas.promote_idea', idea_id=idea.id),
                      'label': 'Notebook', 'icon': 'bi-journal-plus'}
        elif idea.idea_purpose == 'investment' and idea.idea_type == 'company':
            action = {'type': 'evaluate', 'url': url_for('ideas.kill_room', idea_id=idea.id),
                      'label': 'Evaluate', 'icon': 'bi-shield-x'}
        else:
            action = {'type': 'promote', 'url': url_for('ideas.promote_idea', idea_id=idea.id),
                      'label': 'Start', 'icon': 'bi-arrow-right'}

        ideas_data.append({
            'id': idea.id,
            'name': idea.name,
            'ticker': idea.ticker_symbol or '',
            'purpose': idea.idea_purpose or 'investment',
            'state': display_state,
            'age_days': idea_ages.get(idea.id, 0),
            'thesis': (idea.thesis_summary[:80] + '...') if idea.thesis_summary and len(idea.thesis_summary) > 80 else (idea.thesis_summary or ''),
            'source': idea.source or '',
            'action': action,
            'edit_url': url_for('ideas.edit_idea', idea_id=idea.id),
        })
    ideas_json = json.dumps(ideas_data)

    # Serialize ALL checklists for the evaluation modal (pro users can switch)
    checklists_json = json.dumps({
        str(cl.id): {
            'name': cl.name,
            'edit_url': url_for('ideas.edit_kill_checklist', checklist_id=cl.id),
            'criteria': [{
                'id': c.id,
                'question': c.question,
                'help_text': c.help_text or '',
                'failure_reason': c.failure_reason or '',
            } for c in cl.criteria.order_by(KillCriterion.order).all()]
        } for cl in all_kill_checklists
    })

    response = make_response(render_template('inbox.html',
                          title="Idea Inbox",
                          ideas=ideas,
                          ideas_json=ideas_json,
                          checklists_json=checklists_json,
                          default_checklist_id=default_kill_checklist.id,
                          days_since_oldest=days_since_oldest,
                          waiting_count=waiting_count,
                          killing_count=killing_count,
                          ready_count=ready_count,
                          idea_count=len(ideas),
                          ))
    # Prevent caching to ensure fresh data is always loaded
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

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
        submit_action = request.form.get('submit_action', 'inbox')  # 'inbox' or 'start_research'

        # Validation
        if not name:
            flash('Idea name is required', 'error')
            return redirect(url_for('ideas.add_idea'))

        if not source:
            flash('Source is required - please specify where this idea came from', 'error')
            return redirect(url_for('ideas.add_idea'))

        # Handle sector ideas - check if adding directly to notebook
        if idea_type == 'sector':
            add_to_notebook = request.form.get('add_to_notebook') == 'true'

            if add_to_notebook:
                # User chose to add directly to notebook
                # Check if sector notebook already exists
                existing_sector = SectorAnalysis.query.filter_by(
                    user_id=current_user.id,
                    sector_name=name
                ).first()

                if existing_sector:
                    flash(f'Opening existing sector notebook for "{name}"', 'info')
                    return redirect(url_for('sectors.notebook', sector_name=existing_sector.sector_name))
                else:
                    flash(f'Creating sector notebook for "{name}". Add your research notes there!', 'success')
                    # Create new sector notebook
                    new_sector = SectorAnalysis(
                        author=current_user,
                        sector_name=name
                    )
                    db.session.add(new_sector)
                    db.session.commit()

                    # Initialize default sections
                    initialize_default_sections(new_sector)

                    return redirect(url_for('sectors.notebook', sector_name=new_sector.sector_name))
            # If not adding to notebook directly, continue to add to inbox below

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

        # Set status based on action - 'start_research' skips inbox/kill room
        initial_status = 'promoted' if submit_action == 'start_research' else 'inbox'

        new_idea = IdeaPipeline(
            author=current_user, name=name, idea_type=idea_type, idea_purpose=idea_purpose,
            ticker_symbol=ticker_symbol, company_id=company_id, source=source, thesis_summary=thesis,
            initial_notes=notes, status=initial_status
        )

        # If starting research immediately, set promoted timestamp
        if submit_action == 'start_research':
            new_idea.promoted_at = now_utc()

        try:
            db.session.add(new_idea)
            db.session.commit()
            log_research_activity(
                current_user.id,
                'idea_captured',
                idea_id=new_idea.id,
                details={'source': source, 'type': idea_type, 'action': submit_action}
            )

            # Handle "Start Research" flow - redirect to promote page for template selection
            if submit_action == 'start_research':
                flash(f'"{name}" captured! Now select a research template.', 'success')
                return redirect(url_for('ideas.promote_idea', idea_id=new_idea.id))

            flash(f'"{name}" added to your idea inbox!', 'success')
            return redirect(url_for('ideas.inbox'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding idea: {str(e)}', 'error')

    # Get URL parameters for pre-filling and highlighting
    prefill_type = request.args.get('type', '')
    from_start = request.args.get('from_start', '')

    # If coming from start-new flow, show flash message
    if from_start == 'true':
        if prefill_type == 'company':
            flash('Add your company idea here to start the research process', 'info')
        elif prefill_type == 'sector':
            flash('Add your sector idea here to start the research process', 'info')

    return render_template('add_idea.html',
                          title="Quick Capture",
                          prefill_type=prefill_type,
                          from_start=from_start)

@ideas_bp.route('/<int:idea_id>/kill', methods=['POST'])
@login_required
def kill_room(idea_id):
    """Evaluate an idea against kill criteria via the inline modal.

    JSON POST: receives all answers at once, returns JSON result.
    """
    idea = IdeaPipeline.query.get_or_404(idea_id)
    if idea.user_id != current_user.id:
        if request.is_json:
            return json_error('Access denied', 403)
        flash('You do not have access to this idea', 'error')
        return redirect(url_for('ideas.inbox'))

    # ── JSON POST: batch evaluation from inline modal ──────────────
    if request.method == 'POST' and request.is_json:
        data = request.get_json()

        # Quick Kill: custom reason without checklist evaluation
        quick_kill_reason = data.get('quick_kill_reason')
        if quick_kill_reason:
            idea.status = 'killed'
            idea.kill_reason = quick_kill_reason
            idea.killed_at = now_utc()
            db.session.commit()
            log_research_activity(current_user.id, 'idea_killed', idea_id=idea.id,
                                  details={'reason': quick_kill_reason, 'type': 'quick_kill'})
            return jsonify({'success': True, 'outcome': 'killed',
                            'idea_name': idea.name, 'kill_reason': quick_kill_reason})

        if 'answers' not in data:
            return json_error('Missing answers', 400)

        # Resolve checklist — pro users may specify a checklist_id
        checklist_id = data.get('checklist_id')
        if checklist_id:
            checklist = KillChecklist.query.filter_by(id=checklist_id, user_id=current_user.id).first()
        if not checklist_id or not checklist:
            checklist = KillChecklist.query.filter_by(user_id=current_user.id, is_default=True).first()
        if not checklist:
            checklist, _ = ensure_default_checklist(current_user)

        kill_session = KillSession(user_id=current_user.id, idea=idea, checklist=checklist)
        db.session.add(kill_session)

        outcome = 'survived'
        kill_reason = None

        for answer_data in data['answers']:
            criterion = KillCriterion.query.get(answer_data['criterion_id'])
            if not criterion or criterion.kill_checklist_id != checklist.id:
                continue

            passed = answer_data.get('passed', True)
            notes = answer_data.get('notes', '')

            answer = KillAnswer(session=kill_session, criterion=criterion, passed=passed, notes=notes)
            db.session.add(answer)
            criterion.times_evaluated += 1

            if not passed:
                criterion.times_failed += 1
                outcome = 'killed'
                kill_reason = criterion.question
                idea.status = 'killed'
                idea.kill_reason = kill_reason
                idea.failed_criterion = criterion
                idea.killed_at = now_utc()
                break

        kill_session.outcome = outcome
        kill_session.completed_at = now_utc()
        checklist.total_ideas_evaluated += 1

        if outcome == 'survived':
            idea.status = 'survived'
            idea.promoted_at = now_utc()
            log_research_activity(current_user.id, 'idea_promoted', idea_id=idea.id)
        else:
            checklist.total_ideas_killed += 1
            log_research_activity(current_user.id, 'idea_killed', idea_id=idea.id,
                                  details={'reason': kill_reason})

        db.session.commit()

        result = {'success': True, 'outcome': outcome, 'idea_name': idea.name}
        if outcome == 'killed':
            result['kill_reason'] = kill_reason
        else:
            result['promote_url'] = url_for('ideas.promote_idea', idea_id=idea.id)
        return jsonify(result)

@ideas_bp.route('/kill-checklists')
@login_required
@require_feature('kill_checklists')
def manage_kill_checklists():
    """Show kill checklists for the currently logged-in user with pagination and sorting"""
    page = request.args.get('page', 1, type=int)
    per_page = 12  # Show 12 checklists per page
    sort = request.args.get('sort', 'recent')

    # Build query with sorting
    query = KillChecklist.query.filter_by(user_id=current_user.id)

    if sort == 'name':
        query = query.order_by(KillChecklist.name)
    elif sort == 'criteria':
        # Sort by number of criteria
        query = query.outerjoin(KillCriterion).group_by(KillChecklist.id)\
                     .order_by(func.count(KillCriterion.id).desc())
    elif sort == 'oldest':
        query = query.order_by(KillChecklist.created_at)
    else:  # 'recent' is default
        query = query.order_by(KillChecklist.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('manage_kill_checklists.html',
                          title="Kill Checklists",
                          checklists=pagination.items,
                          pagination=pagination)

@ideas_bp.route('/kill-checklists/new', methods=['GET', 'POST'])
@login_required
@require_feature('kill_checklists')
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
        return redirect(url_for('ideas.inbox'))

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
        return redirect(url_for('ideas.inbox'))
    
    return render_template('edit_kill_checklist.html', title="Edit Kill Checklist", checklist=checklist)

@ideas_bp.route('/kill-checklists/<int:checklist_id>/delete', methods=['POST'])
@login_required
@require_feature('kill_checklists')
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

        # Handle sector ideas - create/open sector notebook
        if promotion_action == 'start_sector_research' and idea.idea_type == 'sector':
            # Check if sector notebook already exists
            existing_sector = SectorAnalysis.query.filter_by(
                user_id=current_user.id,
                sector_name=idea.name
            ).first()

            if existing_sector:
                flash(f'Opening existing sector notebook for "{idea.name}"', 'info')
                # Mark idea as promoted
                idea.status = 'promoted'
                idea.promoted_at = now_utc()
                db.session.commit()
                return redirect(url_for('sectors.notebook', sector_name=existing_sector.sector_name))
            else:
                # Create new sector notebook
                new_sector = SectorAnalysis(
                    author=current_user,
                    sector_name=idea.name
                )
                db.session.add(new_sector)
                db.session.flush()

                # Initialize default sections
                initialize_default_sections(new_sector)

                # Mark idea as promoted
                idea.status = 'promoted'
                idea.promoted_at = now_utc()
                db.session.commit()

                flash(f'Sector notebook created for "{idea.name}". Start adding your research!', 'success')
                return redirect(url_for('sectors.notebook', sector_name=new_sector.sector_name))

        elif promotion_action == 'create_company' and idea.idea_type == 'company':
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
            idea.promoted_at = now_utc()
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

            # Get or create company for research project
            company_for_project = idea.promoted_to_company or idea.company

            # If no company exists, create one automatically
            if not company_for_project and idea.idea_type == 'company':
                # Check for existing company with same ticker
                if idea.ticker_symbol:
                    existing = Company.query.filter_by(
                        ticker_symbol=idea.ticker_symbol,
                        user_id=current_user.id
                    ).first()
                    if existing:
                        company_for_project = existing
                        idea.promoted_to_company = existing

                # Create new company if none found
                if not company_for_project:
                    new_company = Company(
                        name=idea.name,
                        ticker_symbol=idea.ticker_symbol,
                        creator=current_user,
                        summary=idea.thesis_summary
                    )
                    db.session.add(new_company)
                    db.session.flush()
                    company_for_project = new_company
                    idea.promoted_to_company = new_company

            # ENFORCE CONSTRAINT: ONE RESEARCH PROJECT PER COMPANY
            if idea.idea_type == 'company' and company_for_project:
                existing_project = ResearchProject.query.filter_by(
                    user_id=current_user.id,
                    company_id=company_for_project.id
                ).filter(
                    ResearchProject.status.in_(['active', 'paused'])
                ).first()

                if existing_project:
                    flash(f'You already have a research project for {company_for_project.name}. Only one project per company is allowed.', 'error')
                    return redirect(url_for('research_workflow.project_dashboard', project_id=existing_project.id))

            # Ensure we have a company for the research project
            if not company_for_project:
                flash('Company selection is required for research projects', 'error')
                return redirect(url_for('ideas.promote_idea', idea_id=idea.id))

            project = ResearchProject(
                researcher=current_user,
                template=template,
                company_id=company_for_project.id,
                project_name=f"{idea.name} - {template.name}",
                status='active',
                idea=idea,
                investment_thesis=idea.thesis_summary,
                workflow_snapshot=copy.deepcopy(template.workflow_steps)
            )
            
            # Update template usage count
            template.times_used += 1
            
            try:
                db.session.add(project)
                idea.status = 'promoted'
                idea.promoted_at = now_utc()
                db.session.commit()
                
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
    
    # Ensure the user has at least one template (creates default if needed)
    ensure_default_template(current_user)

    # Get available templates for the GET request
    templates = current_user.research_templates.filter_by(is_active=True).order_by(ResearchTemplate.times_used.desc()).all()

    return render_template('promote_idea.html',
                          title=f"Start Research: {idea.name}",
                          idea=idea,
                          templates=templates)

@ideas_bp.route('/<int:idea_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_idea(idea_id):
    idea = IdeaPipeline.query.get_or_404(idea_id)
    if idea.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('ideas.inbox'))

    # Get return URL from query parameter, default to inbox
    return_to = request.args.get('return_to', 'inbox')

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
                return redirect(url_for('ideas.edit_idea', idea_id=idea.id, return_to=return_to))

            # Check existing ideas (excluding current idea)
            existing_idea = IdeaPipeline.query.filter(
                IdeaPipeline.ticker_symbol == new_ticker,
                IdeaPipeline.user_id == current_user.id,
                IdeaPipeline.id != idea.id
            ).first()
            if existing_idea:
                flash(f'You already have an idea with ticker {new_ticker}: {existing_idea.name} (Status: {existing_idea.status}). Cannot change to this ticker.', 'error')
                return redirect(url_for('ideas.edit_idea', idea_id=idea.id, return_to=return_to))

        idea.ticker_symbol = new_ticker
        idea.source = request.form.get('source')
        idea.thesis_summary = request.form.get('thesis_summary')
        idea.initial_notes = request.form.get('initial_notes')

        try:
            db.session.commit()
            flash('Idea updated successfully', 'success')
            # Route back to the appropriate page
            if return_to == 'graveyard':
                return redirect(url_for('research_workflow.my_projects'))
            else:
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
                           exchanges=EXCHANGES, base_ticker=base_ticker, exchange_suffix=exchange_suffix,
                           return_to=return_to)

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
        return json_unauthorized('Access denied')

    idea.status = 'inbox'
    idea.kill_reason = None
    idea.failed_criterion_id = None
    idea.killed_at = None

    try:
        db.session.commit()
        return json_success()
    except Exception as e:
        db.session.rollback()
        return json_error(str(e), status_code=500)

@ideas_bp.route('/<int:idea_id>/mark_someday', methods=['GET'])
@login_required
def mark_someday(idea_id):
    idea = IdeaPipeline.query.get_or_404(idea_id)
    if idea.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('ideas.inbox'))
    
    idea.status = 'someday'
    idea.last_reviewed_at = now_utc()
    
    try:
        db.session.commit()
        flash(f'"{idea.name}" moved to Someday/Maybe', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating idea: {str(e)}', 'error')
    
    return redirect(url_for('ideas.inbox'))

@ideas_bp.route('/kill-checklists/<int:checklist_id>/set-default', methods=['POST'])
@login_required
@require_feature('kill_checklists')
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


# ===============================================
# DYNAMIC KILL CHECKLIST - INTELLIGENT FEATURES
# ===============================================

@ideas_bp.route('/api/kill-checklist/<int:checklist_id>/suggestions')
@login_required
def get_checklist_suggestions(checklist_id):
    """Get intelligent suggestions for optimizing a kill checklist"""
    try:
        checklist = KillChecklist.query.filter_by(
            id=checklist_id,
            user_id=current_user.id
        ).first()

        if not checklist:
            return json_error('Checklist not found', status_code=404)

        # Get pending suggestions for this checklist
        suggestions = KillChecklistSuggestion.query.filter_by(
            kill_checklist_id=checklist_id,
            user_id=current_user.id,
            status='pending'
        ).order_by(KillChecklistSuggestion.effectiveness_gain.desc()).all()

        # Convert to JSON format
        suggestions_data = []
        for suggestion in suggestions:
            suggestions_data.append({
                'id': suggestion.id,
                'type': suggestion.suggestion_type,
                'title': suggestion.title,
                'description': suggestion.description,
                'reasoning': suggestion.reasoning,
                'effectiveness_gain': suggestion.effectiveness_gain,
                'confidence_score': suggestion.confidence_score,
                'created_at': suggestion.created_at.isoformat(),
                'age_hours': suggestion.age_hours,
                'suggestion_data': suggestion.suggestion_data
            })

        return jsonify({
            'suggestions': suggestions_data,
            'checklist_stats': {
                'total_evaluations': checklist.total_ideas_evaluated,
                'kill_rate': checklist.kill_rate,
                'criteria_count': checklist.criteria_count
            }
        })

    except Exception as e:
        return json_error(str(e), status_code=500)


@ideas_bp.route('/api/kill-checklist/<int:checklist_id>/analyze', methods=['POST'])
@login_required
def analyze_checklist(checklist_id):
    """Trigger analysis and generate new suggestions for a kill checklist"""
    try:
        checklist = KillChecklist.query.filter_by(
            id=checklist_id,
            user_id=current_user.id
        ).first()

        if not checklist:
            return json_error('Checklist not found', status_code=404)

        # Generate reordering suggestions
        reorder_suggestion = KillChecklistAnalytics.suggest_reordering(checklist_id)
        suggestions_created = 0

        if reorder_suggestion:
            db.session.add(reorder_suggestion)
            suggestions_created += 1

        # Generate cleanup suggestions
        cleanup_suggestions = KillChecklistAnalytics._suggest_cleanup(checklist_id)
        for suggestion in cleanup_suggestions:
            db.session.add(suggestion)
            suggestions_created += 1

        db.session.commit()

        return jsonify({
            'message': f'Analysis complete. {suggestions_created} new suggestions generated.',
            'suggestions_created': suggestions_created
        })

    except Exception as e:
        db.session.rollback()
        return json_error(str(e), status_code=500)


@ideas_bp.route('/api/suggestions/<int:suggestion_id>/apply', methods=['POST'])
@login_required
def apply_suggestion(suggestion_id):
    """Apply a suggestion to optimize the kill checklist"""
    try:
        success = SuggestionEngine.apply_suggestion(suggestion_id, current_user.id)

        if success:
            return jsonify({'message': 'Suggestion applied successfully'})
        else:
            return json_error('Failed to apply suggestion')

    except Exception as e:
        return json_error(str(e), status_code=500)


@ideas_bp.route('/api/suggestions/<int:suggestion_id>/reject', methods=['POST'])
@login_required
def reject_suggestion(suggestion_id):
    """Reject a suggestion"""
    try:
        suggestion = KillChecklistSuggestion.query.filter_by(
            id=suggestion_id,
            user_id=current_user.id,
            status='pending'
        ).first()

        if not suggestion:
            return json_error('Suggestion not found', status_code=404)

        suggestion.status = 'rejected'
        suggestion.responded_at = now_utc()
        db.session.commit()

        return jsonify({'message': 'Suggestion rejected'})

    except Exception as e:
        db.session.rollback()
        return json_error(str(e), status_code=500)


@ideas_bp.route('/api/kill-checklist/<int:checklist_id>/effectiveness')
@login_required
def get_effectiveness_analysis(checklist_id):
    """Get detailed effectiveness analysis for a kill checklist"""
    try:
        checklist = KillChecklist.query.filter_by(
            id=checklist_id,
            user_id=current_user.id
        ).first()

        if not checklist:
            return json_error('Checklist not found', status_code=404)

        # Analyze each criterion
        criteria_analysis = []
        for criterion in checklist.criteria.order_by(KillCriterion.order):
            # Calculate/update effectiveness score
            effectiveness = KillChecklistAnalytics.calculate_criterion_effectiveness(criterion.id)

            criteria_analysis.append({
                'id': criterion.id,
                'question': criterion.question,
                'order': criterion.order,
                'times_evaluated': criterion.times_evaluated,
                'times_failed': criterion.times_failed,
                'failure_rate': criterion.failure_rate,
                'effectiveness_score': effectiveness,
                'last_used': criterion.last_used.isoformat() if criterion.last_used else None,
                'auto_suggested': criterion.auto_suggested,
                'has_source_mistake': criterion.source_mistake_id is not None
            })

        return jsonify({
            'checklist': {
                'id': checklist.id,
                'name': checklist.name,
                'total_evaluations': checklist.total_ideas_evaluated,
                'total_kills': checklist.total_ideas_killed,
                'kill_rate': checklist.kill_rate
            },
            'criteria_analysis': criteria_analysis,
            'recommendations': {
                'most_effective': max(criteria_analysis, key=lambda x: x['effectiveness_score'])['question'] if criteria_analysis else None,
                'least_effective': min(criteria_analysis, key=lambda x: x['effectiveness_score'])['question'] if criteria_analysis else None,
                'underutilized': [c['question'] for c in criteria_analysis if c['times_evaluated'] < 5]
            }
        })

    except Exception as e:
        return json_error(str(e), status_code=500)


@ideas_bp.route('/api/mistake-log/<int:mistake_id>/suggest-criteria', methods=['POST'])
@login_required
def suggest_criteria_from_mistake(mistake_id):
    """Analyze a mistake and suggest kill criteria to prevent similar issues"""
    try:
        mistake = MistakeLog.query.filter_by(
            id=mistake_id,
            user_id=current_user.id
        ).first()

        if not mistake:
            return json_error('Mistake not found', status_code=404)

        # Generate suggestion from mistake
        suggestion = KillChecklistAnalytics.analyze_mistake_for_criteria(mistake_id)

        if suggestion:
            db.session.add(suggestion)
            db.session.commit()

            return jsonify({
                'message': 'Suggestion generated from mistake analysis',
                'suggestion': {
                    'id': suggestion.id,
                    'title': suggestion.title,
                    'description': suggestion.description,
                    'suggested_criterion': suggestion.suggestion_data.get('new_criterion', {}).get('question')
                }
            })
        else:
            return jsonify({
                'message': 'No actionable criteria could be extracted from this mistake',
                'reason': 'The mistake description may not contain specific patterns that can be converted to kill criteria'
            })

    except Exception as e:
        db.session.rollback()
        return json_error(str(e), status_code=500)


# Webhook for milestone-based suggestions (called from kill session completion)
def trigger_milestone_analysis(user_id, checklist_id, evaluation_count):
    """Trigger milestone-based analysis (called internally)"""
    try:
        SuggestionEngine.process_evaluation_milestone(user_id, checklist_id, evaluation_count)
    except Exception as e:
        print(f"Error in milestone analysis: {e}")


# Webhook for mistake-based suggestions (called when mistake is logged)
def trigger_mistake_analysis(mistake_id):
    """Trigger mistake-based analysis (called internally)"""
    try:
        SuggestionEngine.process_mistake_logged(mistake_id)
    except Exception as e:
        print(f"Error in mistake analysis: {e}")