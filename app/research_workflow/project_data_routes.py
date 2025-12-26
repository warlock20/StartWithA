"""
Project Data Routes Module

This module handles all routes related to project content and data including:
- Viewing project notes and summaries
- Saving project decisions
- Adding findings (green/red flags)
- Updating investment thesis

Extracted from routes.py lines: 189-226, 228-251, 253-303, 314-334, 337-370
"""

from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from app import db
from app.models import ResearchTemplate, ResearchProject, Sector, ChecklistAnalysis
from app.research_workflow import research_workflow_bp
from app.services.too_hard_service import TooHardBasketService
from app.utils.time_utils import now_utc


@research_workflow_bp.route('/projects/<int:project_id>/notes')
@login_required
def view_project_notes(project_id):
    """View all research notes for a project"""
    project = ResearchProject.query.get_or_404(project_id)

    # Authorization check
    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    # Get all step notes
    step_notes = project.step_notes or {}

    # Get template steps for context
    template_steps = project.template.workflow_steps if project.template else []

    # Combine notes with step information
    notes_with_context = []
    for step_index, notes in step_notes.items():
        step_idx = int(step_index)
        step_name = "Unknown Step"
        if step_idx < len(template_steps):
            step_name = template_steps[step_idx].get('name', f'Step {step_idx + 1}')

        notes_with_context.append({
            'step_index': step_idx,
            'step_name': step_name,
            'notes': notes
        })

    # Sort by step index
    notes_with_context.sort(key=lambda x: x['step_index'])

    return render_template('project_notes.html',
                          title=f"Research Notes - {project.research_subject_name}",
                          project=project,
                          notes_with_context=notes_with_context)


@research_workflow_bp.route('/projects/<int:project_id>/summary')
@login_required
def project_summary(project_id):
    """Show summary and decision page for completed project"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    # Compile all notes and findings
    all_notes = []
    for step_index, notes in (project.step_notes or {}).items():
        step = project.template.get_step(int(step_index))
        if step and notes:
            all_notes.append({
                'step_index': int(step_index),
                'step_name': step['name'],
                'step_type': step.get('type'),
                'notes': notes
            })

    # Add investment thesis as a note if it exists but wasn't added
    if project.investment_thesis and project.template.workflow_steps:
        # Find the thesis step
        for step_index, step in enumerate(project.template.workflow_steps):
            if step.get('type') == 'thesis_writing':
                # Check if this step already has notes
                has_notes = any(n['step_index'] == step_index for n in all_notes)
                if not has_notes:
                    all_notes.append({
                        'step_index': step_index,
                        'step_name': step['name'],
                        'step_type': 'thesis_writing',
                        'notes': f"**Investment Thesis:**\n\n{project.investment_thesis}"
                    })
                break

    # Sort notes by step index
    all_notes.sort(key=lambda x: x['step_index'])

    # Get checklist analyses for step links
    checklist_analyses = {}
    if project.template and project.template.workflow_steps:
        for step_index in project.completed_steps:
            if step_index < len(project.template.workflow_steps):
                step = project.template.workflow_steps[step_index]
                if step.get('type') == 'checklist':
                    checklist_id = step.get('config', {}).get('checklist_id')
                    if checklist_id:
                        analysis = ChecklistAnalysis.query.filter_by(
                            user_id=current_user.id,
                            checklist_id=int(checklist_id),
                            company_id=project.company_id
                        ).order_by(ChecklistAnalysis.start_date.desc()).first()
                        if analysis:
                            checklist_analyses[step_index] = analysis.id

    return render_template('project_summary.html',
                          title=f"Summary: {project.project_name}",
                          project=project,
                          all_notes=all_notes,
                          checklist_analyses=checklist_analyses)


@research_workflow_bp.route('/projects/<int:project_id>/decision', methods=['POST'])
@login_required
def save_decision(project_id):
    """Save final investment decision for a project"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    # --- Get form data ---
    decision = request.form.get('decision')
    project.decision = decision  # Save the decision to the project
    project.decision_confidence = request.form.get('confidence', type=int)
    project.decision_date = now_utc()

    # Parse key findings
    green_flags = request.form.get('green_flags', '').split('\n')
    red_flags = request.form.get('red_flags', '').split('\n')
    project.green_flags = [f.strip() for f in green_flags if f.strip()]
    project.red_flags = [f.strip() for f in red_flags if f.strip()]

    # Update template success metrics
    if project.decision == 'invest':
        project.template.successful_investments += 1
    elif project.decision == 'pass':
        project.template.failed_investments += 1

    # --- Add company to watchlist if decision is watchlist ---
    flash_message = 'Decision saved!'  # Default message

    if decision == 'watchlist' and project.company:
        company_to_watch = project.company
        if company_to_watch not in current_user.favorites:
            current_user.favorites.append(company_to_watch)
            flash_message = f'Decision saved. "{company_to_watch.name}" has been added to your Favorites/Watchlist.'

    try:
        db.session.commit()
        flash(flash_message, 'success')  # Use the dynamic flash message

        if project.decision == 'invest':
            # Redirect to portfolio or next steps
            return redirect(url_for('companies.companies_dashboard'))
        else:
            # Back to project list
            return redirect(url_for('research_workflow.my_projects'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error saving decision: {str(e)}', 'error')
        return redirect(request.referrer)


@research_workflow_bp.route('/projects/<int:project_id>/update-thesis', methods=['POST'])
@login_required
def update_thesis(project_id):
    """Update the investment thesis for a research project"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    thesis = request.form.get('investment_thesis', '').strip()
    project.investment_thesis = thesis
    project.last_worked_at = now_utc()

    # Also update step_notes for the thesis_writing step to keep them in sync
    if project.template and project.template.workflow_steps:
        for step_index, step in enumerate(project.template.workflow_steps):
            if step.get('type') == 'thesis_writing':
                if not project.step_notes:
                    project.step_notes = {}
                # Update step notes with the thesis
                project.step_notes[str(step_index)] = f"**Investment Thesis:**\n\n{thesis}"
                break

    try:
        db.session.commit()
        flash('Investment thesis updated', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating thesis: {str(e)}', 'error')

    return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))


@research_workflow_bp.route('/projects/<int:project_id>/add-finding', methods=['POST'])
@login_required
def add_finding(project_id):
    """Add a key finding to a research project"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    finding_type = request.form.get('finding_type')  # 'green_flag' or 'red_flag'
    finding_text = request.form.get('finding_text', '').strip()

    if not finding_text:
        flash('Finding text is required', 'error')
        return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))

    if finding_type == 'green_flag':
        if not project.green_flags:
            project.green_flags = []
        project.green_flags = project.green_flags + [finding_text]
        flag_label = 'Green flag'
    elif finding_type == 'red_flag':
        if not project.red_flags:
            project.red_flags = []
        project.red_flags = project.red_flags + [finding_text]
        flag_label = 'Red flag'
    else:
        flash('Invalid finding type', 'error')
        return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))

    project.last_worked_at = now_utc()

    try:
        db.session.commit()
        flash(f'{flag_label} added successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding finding: {str(e)}', 'error')

    return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))


@research_workflow_bp.route('/too-hard-basket')
@login_required
def too_hard_basket():
    """Unified page showing all rejected companies from all sources"""
    # Get filter parameters
    rejection_stage = request.args.get('stage')  # 'kill_checklist', 'mid_research', 'full_analysis'
    sector_filter = request.args.get('sector')
    coc_filter = request.args.get('coc')  # 'yes', 'no', 'unsure'
    search_query = request.args.get('search', '').strip()
    sort_by = request.args.get('sort', 'recent')  # 'recent', 'oldest', 'time', 'confidence'
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    # Get ALL items first for accurate counts (without filters except user_id)
    all_items = TooHardBasketService.get_all_too_hard_companies(current_user.id, {})

    # Calculate statistics from ALL items (not filtered)
    total_count = len(all_items)
    kill_count = sum(1 for item in all_items if item.rejection_stage == 'kill_checklist')
    mid_research_count = sum(1 for item in all_items if item.rejection_stage == 'mid_research')
    full_analysis_count = sum(1 for item in all_items if item.rejection_stage == 'full_analysis')

    # Get unique sectors from ALL items for filter dropdown
    all_sectors = set(item.sector for item in all_items if item.sector)
    sectors_list = sorted(list(all_sectors))

    # Now build filters for displaying items
    filters = {}
    if rejection_stage:
        filters['rejection_stage'] = rejection_stage
    if sector_filter:
        filters['sector'] = sector_filter
    if coc_filter:
        filters['within_coc'] = coc_filter
    if search_query:
        filters['search'] = search_query

    # Get filtered items for display
    too_hard_items = TooHardBasketService.get_all_too_hard_companies(current_user.id, filters)

    # Apply sorting
    if sort_by == 'oldest':
        too_hard_items.sort(key=lambda x: x.rejection_date or now_utc())
    elif sort_by == 'time':
        too_hard_items.sort(key=lambda x: x.time_invested_hours or 0, reverse=True)
    elif sort_by == 'confidence':
        too_hard_items.sort(key=lambda x: x.confidence or 0, reverse=True)
    # Default is 'recent' which is already sorted by TooHardBasketService

    # Pagination
    total_filtered = len(too_hard_items)
    total_pages = (total_filtered + per_page - 1) // per_page  # Ceiling division
    page = max(1, min(page, total_pages if total_pages > 0 else 1))

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_items = too_hard_items[start_idx:end_idx]

    # Create pagination object similar to Flask-SQLAlchemy
    class SimplePagination:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1 if self.has_prev else None
            self.next_num = page + 1 if self.has_next else None

        def iter_pages(self, left_edge=2, left_current=2, right_current=2, right_edge=2):
            last = 0
            for num in range(1, self.pages + 1):
                if num <= left_edge or \
                   (num >= self.page - left_current and num <= self.page + right_current) or \
                   num > self.pages - right_edge:
                    if last + 1 != num:
                        yield None
                    yield num
                    last = num

    pagination = SimplePagination(paginated_items, page, per_page, total_filtered)

    return render_template('too_hard_basket.html',
                         title='Too Hard Basket',
                         too_hard_items=paginated_items,
                         pagination=pagination,
                         total_count=total_count,
                         kill_count=kill_count,
                         mid_research_count=mid_research_count,
                         full_analysis_count=full_analysis_count,
                         sectors_list=sectors_list,
                         current_stage=rejection_stage,
                         current_sector=sector_filter,
                         current_coc=coc_filter,
                         search_query=search_query,
                         sort_by=sort_by,
                         current_per_page=per_page)
