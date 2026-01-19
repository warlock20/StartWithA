"""
Project Workflow Execution Routes Module

This module handles all routes related to executing research project workflows:
- Starting projects
- Viewing project dashboard
- Executing workflow steps
- Completing steps
- Completing research (checklist) steps
- Skipping steps
- Returning from checklist execution
"""

from flask import render_template, request, redirect, url_for, flash, jsonify, session as flask_session
from flask_login import current_user, login_required
from app import db
from app.models import (ResearchTemplate, ResearchProject, WorkSession,
                       Company, Checklist, KillChecklist, IdeaPipeline,
                       ChecklistAnalysis, ChecklistAnswer, ThesisEvolution)
from app.research_workflow import research_workflow_bp
from app.analytics.utils import log_research_activity
from app.utils.time_utils import now_utc, ensure_timezone_aware, calculate_duration_minutes, format_for_javascript
from app.research.routes import get_all_ordered_items_for_checklist
from app.services.sector_service import SectorService
from sqlalchemy.orm.attributes import flag_modified
import json
import logging

logger = logging.getLogger(__name__)

# Import helper function from helpers module
from app.research_workflow.helpers import collect_research_session_summary


@research_workflow_bp.route('/projects/start', methods=['POST'])
@login_required
def start_project():
    """Start a new research project for a company using a template"""
    template_id = request.form.get('template_id', type=int)
    company_id = request.form.get('company_id', type=int)

    # Validate inputs
    if not template_id:
        flash('Template selection is required', 'error')
        return redirect(request.referrer or url_for('research_workflow.template_list'))

    if not company_id:
        flash('Company selection is required', 'error')
        return redirect(request.referrer or url_for('research_workflow.template_list'))

    # Verify template ownership
    template = ResearchTemplate.query.get_or_404(template_id)
    if template.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.template_list'))

    # Get company
    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.template_list'))

    # ENFORCE CONSTRAINT: ONE RESEARCH PROJECT PER COMPANY (regardless of template)
    existing_project = ResearchProject.query.filter_by(
        user_id=current_user.id,
        company_id=company_id
    ).filter(
        ResearchProject.status.in_(['active', 'paused'])
    ).first()

    if existing_project:
        if existing_project.status == 'active':
            flash(f'You already have an active research project for {company.name}. Only one project per company is allowed.', 'error')
            return redirect(url_for('research_workflow.project_dashboard', project_id=existing_project.id))
        elif existing_project.status == 'paused':
            flash(f'You have a paused research project for {company.name}. Resume it or delete it to start a new one.', 'warning')
            return redirect(url_for('research_workflow.project_dashboard', project_id=existing_project.id))

    # Create new project
    project = ResearchProject(
        researcher=current_user,
        template=template,
        company=company,
        project_name=f"{company.name} - {template.name}",
        status='active'
    )

    # If this came from an idea pipeline, link it
    idea_id = request.form.get('idea_id', type=int)
    if idea_id:
        idea = IdeaPipeline.query.get(idea_id)
        if idea and idea.user_id == current_user.id:
            project.idea = idea
            project.investment_thesis = idea.thesis_summary

    try:
        db.session.add(project)
        db.session.commit()
        log_research_activity(
            current_user.id,
            'research_started',
            company_id=company.id if company else None,
            project_id=project.id
        )
        flash(f'Research project started for {company.name}!', 'success')
        return redirect(url_for('research_workflow.project_dashboard', project_id=project.id))
    except Exception as e:
        db.session.rollback()
        flash(f'Error starting project: {str(e)}', 'error')
        return redirect(request.referrer or url_for('companies.companies_dashboard'))


@research_workflow_bp.route('/projects/<int:project_id>')
@login_required
def project_dashboard(project_id):
    """Main dashboard for a research project"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    # Get recent work sessions
    recent_sessions = project.work_sessions.order_by(
        WorkSession.start_time.desc()
    ).limit(5).all()

    # Calculate time spent per step
    time_breakdown = {}
    for step_index, minutes in (project.time_per_step or {}).items():
        step = project.template.get_step(int(step_index))
        if step:
            time_breakdown[step['name']] = minutes

    # Get next steps
    next_steps = []
    if project.template.workflow_steps:
        for i, step in enumerate(project.template.workflow_steps):
            if i not in project.completed_steps:
                next_steps.append(step)
                if len(next_steps) >= 3:  # Show next 3 upcoming steps
                    break

    # Get latest research session for the company (for checklist analysis button)
    latest_research_session = None
    if project.company_id:
        latest_research_session = ChecklistAnalysis.query.filter_by(
            company_id=project.company_id,
            user_id=current_user.id,
            status='completed'
        ).order_by(ChecklistAnalysis.start_date.desc()).first()

    # Calculate days since last work using proper timezone handling
    days_since_last_work = None
    if project.last_worked_at:
        last_worked_aware = ensure_timezone_aware(project.last_worked_at)
        current_time = now_utc()
        days_since_last_work = (current_time - last_worked_aware).days

    # Get checklist analysis IDs for completed checklist steps
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

    return render_template('project_dashboard.html',
                          title=f"Research: {project.project_name}",
                          project=project,
                          recent_sessions=recent_sessions,
                          time_breakdown=time_breakdown,
                          next_steps=next_steps,
                          latest_research_session=latest_research_session,
                          days_since_last_work=days_since_last_work,
                          checklist_analyses=checklist_analyses)


@research_workflow_bp.route('/projects/<int:project_id>/execute/<int:step_index>')
@login_required
def execute_step(project_id, step_index):
    """Execute a specific step in the research workflow"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    # Get the step details
    step = project.template.get_step(step_index)
    if not step:
        flash('Invalid step', 'error')
        return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))

    # Check for existing active session for this step
    existing_session = WorkSession.query.filter_by(
        research_project_id=project_id,
        user_id=current_user.id,
        step_index=step_index,
        end_time=None
    ).first()

    if existing_session:
        # Reuse existing active session
        session = existing_session
    else:
        # Create new session
        session = WorkSession(
            project=project,
            user=current_user,
            step_index=step_index,
            step_name=step['name'],
            start_time=now_utc()
        )
        db.session.add(session)
        db.session.commit()

    # Route to appropriate handler based on step type
    if step['type'] == 'checklist':
        # Handle investment checklist reference - redirect to research session evaluation
        # Check for step override first (in case checklist was replaced)
        checklist_id = None
        if project.step_overrides and str(step_index) in project.step_overrides:
            checklist_id = project.step_overrides[str(step_index)].get('checklist_id')

        # Fall back to template config
        if not checklist_id:
            checklist_id = step['config'].get('checklist_id')
        if checklist_id:
            checklist = Checklist.query.get(checklist_id)
            if checklist and checklist.user_id == current_user.id:
                # Check if project has a company (required for research sessions)
                if not project.company_id:
                    flash('Research project must have a company assigned to use investment checklists. Please assign a company to this project first.', 'error')
                    return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))

                # Verify the company still exists in the database
                company = Company.query.get(project.company_id)
                if not company:
                    flash(f'The company associated with this project (ID: {project.company_id}) no longer exists. Please update the project.', 'error')
                    return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))

                # Check if a research session already exists for this checklist and company
                existing_research_session = ChecklistAnalysis.query.filter_by(
                    user_id=current_user.id,
                    checklist_id=checklist_id,
                    company_id=project.company_id
                ).first()

                if existing_research_session:
                    # If session exists and is in progress, find the first unanswered item
                    if existing_research_session.status == 'in_progress':
                        all_items = get_all_ordered_items_for_checklist(checklist_id)

                        if all_items:
                            # Find first unanswered item
                            redirect_to_item_id = all_items[0].id  # Default to first item
                            for item in all_items:
                                answer_exists = ChecklistAnswer.query.filter_by(
                                    checklist_analysis_id=existing_research_session.id,
                                    checklist_item_id=item.id
                                ).first()
                                if not answer_exists:
                                    redirect_to_item_id = item.id
                                    break

                            # Store research context for potential return
                            flask_session['research_context'] = {
                                'project_id': project_id,
                                'step_index': step_index,
                                'workflow_session_id': session.id if session else None
                            }

                            return redirect(url_for('research.research_step',
                                                  analysis_id=existing_research_session.id,
                                                  item_id=redirect_to_item_id))
                        else:
                            flash('Investment checklist has no items to evaluate', 'warning')
                            return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))

                    elif existing_research_session.status == 'completed':
                        # Store research context even for completed checklists
                        flask_session['research_context'] = {
                            'project_id': project_id,
                            'step_index': step_index,
                            'workflow_session_id': session.id if session else None
                        }
                        flash('Investment checklist research already completed. Viewing summary.', 'info')
                        return redirect(url_for('research.view_checklist_session_summary',
                                              analysis_id=existing_research_session.id))
                else:
                    # Create new research session
                    new_research_session = ChecklistAnalysis(
                        user_id=current_user.id,
                        checklist_id=checklist_id,
                        company_id=project.company_id,
                        status='in_progress'
                    )

                    try:
                        db.session.add(new_research_session)
                        db.session.commit()

                        # Get first item and redirect to it
                        all_items = get_all_ordered_items_for_checklist(checklist_id)

                        if all_items:
                            # Store research context for potential return
                            flask_session['research_context'] = {
                                'project_id': project_id,
                                'step_index': step_index,
                                'workflow_session_id': session.id if session else None
                            }

                            return redirect(url_for('research.research_step',
                                                  analysis_id=new_research_session.id,
                                                  item_id=all_items[0].id))
                        else:
                            flash('Investment checklist has no items to evaluate', 'warning')
                            return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))

                    except Exception as e:
                        db.session.rollback()
                        flash(f'Error starting research session: {str(e)}', 'error')
                        return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))
            else:
                # Checklist was deleted or not found - offer to select a new one
                flash('The investment checklist for this step is no longer available. Please select a new checklist to continue.', 'warning')
                user_checklists = current_user.checklists.all()
                return render_template('select_checklist.html',
                                     title=f"Select Checklist: {step['name']}",
                                     project=project,
                                     step=step,
                                     step_index=step_index,
                                     session=session,
                                     user_checklists=user_checklists)
        else:
            # No checklist configured - offer to select one
            flash('No investment checklist configured for this step. Please select one to continue.', 'info')
            user_checklists = current_user.checklists.all()
            return render_template('select_checklist.html',
                                 title=f"Select Checklist: {step['name']}",
                                 project=project,
                                 step=step,
                                 step_index=step_index,
                                 session=session,
                                 user_checklists=user_checklists)

    elif step['type'] == 'kill_checklist_reference':
        # Handle kill checklist reference
        kill_checklist_id = step['config'].get('kill_checklist_id')
        if kill_checklist_id:
            kill_checklist = KillChecklist.query.get(kill_checklist_id)
            if kill_checklist and kill_checklist.user_id == current_user.id:
                return render_template('execute_kill_checklist_step.html',
                                    title=f"Execute: {step['name']}",
                                    project=project,
                                    step=step,
                                    step_index=step_index,
                                    session=session,
                                    kill_checklist=kill_checklist)
            else:
                flash('Kill checklist not found or access denied', 'error')
                return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))
        else:
            flash('No kill checklist configured for this step', 'warning')
            return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))

    elif step['type'] == 'model':
        model_type = step['config'].get('model_type')
        if model_type == 'SWOT Analysis':
            return redirect(url_for('companies.swot_analysis',
                                  company_id=project.company_id,
                                  project_id=project_id,
                                  step_index=step_index))
        elif model_type == 'Porter\'s Five Forces':
            return redirect(url_for('companies.porters_five_forces_analysis',
                                  company_id=project.company_id,
                                  project_id=project_id,
                                  step_index=step_index))

    elif step['type'] == 'competitor_analysis':
        return redirect(url_for('research_workflow.competitor_analysis_step',
                              project_id=project_id, step_index=step_index))

    # For other step types, show the generic execution interface
    # Format session start time for JavaScript timer
    session_start_js = format_for_javascript(session.start_time)

    # Get existing notes for this step
    # For thesis_writing steps, use project.investment_thesis
    # For other steps, use project.step_notes[step_index]
    existing_notes = None
    if step['type'] == 'thesis_writing':
        existing_notes = project.investment_thesis or ''
    else:
        if project.step_notes and str(step_index) in project.step_notes:
            existing_notes = project.step_notes[str(step_index)]

    return render_template('execute_step.html',
                          title=f"Execute: {step['name']}",
                          project=project,
                          step=step,
                          step_index=step_index,
                          session=session,
                          session_start_js=session_start_js,
                          existing_notes=existing_notes)


@research_workflow_bp.route('/projects/<int:project_id>/complete-step', methods=['POST'])
@login_required
def complete_step(project_id):
    """Mark a step as complete and save notes"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    step_index = request.form.get('step_index', type=int)
    notes = request.form.get('notes')
    session_id = request.form.get('session_id', type=int)

    # Complete the work session
    if session_id:
        session = WorkSession.query.get(session_id)
        if session and session.user_id == current_user.id:
            session.end_time = now_utc()
            session.duration_minutes = calculate_duration_minutes(
                session.start_time, session.end_time
            )
            session.notes = notes

            # Update project time tracking
            if not project.time_per_step:
                project.time_per_step = {}

            current_time = project.time_per_step.get(str(step_index), 0)
            project.time_per_step[str(step_index)] = current_time + session.duration_minutes
            project.total_hours_spent += session.duration_minutes / 60

    # Mark step as complete
    if not project.completed_steps:
        project.completed_steps = []

    if step_index not in project.completed_steps:
        project.completed_steps = project.completed_steps + [step_index]

    # Save step notes
    if not project.step_notes:
        project.step_notes = {}
    project.step_notes[str(step_index)] = notes

    # If this is a thesis_writing step, also update project.investment_thesis
    if project.template and project.template.workflow_steps and step_index < len(project.template.workflow_steps):
        step = project.template.workflow_steps[step_index]
        if step.get('type') == 'thesis_writing':
            # Extract plain text from BlockNote JSON if needed
            try:
                blocks = json.loads(notes) if notes else []
                # Extract text from BlockNote blocks
                thesis_text = []
                for block in blocks:
                    if block.get('type') == 'paragraph':
                        content = block.get('content', [])
                        paragraph_text = ''.join(item.get('text', '') for item in content if item.get('type') == 'text')
                        if paragraph_text.strip():
                            thesis_text.append(paragraph_text)
                    elif block.get('type') == 'heading':
                        content = block.get('content', [])
                        heading_text = ''.join(item.get('text', '') for item in content if item.get('type') == 'text')
                        if heading_text.strip():
                            thesis_text.append(heading_text)
                project.investment_thesis = '\n\n'.join(thesis_text) if thesis_text else notes
            except (json.JSONDecodeError, TypeError):
                # If not JSON, use as-is
                project.investment_thesis = notes

            # Create ThesisEvolution Version 0 (initial thesis from research)
            # Check if version 0 already exists for this company
            existing_v0 = ThesisEvolution.query.filter_by(
                user_id=current_user.id,
                company_id=project.company_id,
                version=0
            ).first()

            if not existing_v0 and project.investment_thesis:
                thesis_evolution = ThesisEvolution(
                    user_id=current_user.id,
                    company_id=project.company_id,
                    version=0,
                    thesis=project.investment_thesis,
                    change_summary='Initial investment thesis from research project',
                    change_trigger=f'Research project: {project.project_name}',
                    conviction_level=project.decision_confidence,  # Set from research decision
                    is_current=True,
                    created_at=now_utc()
                )
                db.session.add(thesis_evolution)
                logger.info(f"Created ThesisEvolution v0 for company {project.company_id} from research project {project.id}")

    # Update project progress
    project.last_worked_at = now_utc()

    # Move to next step or complete project
    if step_index + 1 < len(project.template.workflow_steps):
        project.current_step_index = step_index + 1
    else:
        project.status = 'completed'
        project.completed_at = now_utc()
        flash('Research project completed! Time to make your investment decision.', 'success')

    try:
        db.session.commit()
        completed_count = current_user.research_projects.filter_by(status='completed').count()
        if completed_count % 5 == 0:  # Every 5 completions
            flash('You have enough data for pattern recognition. Visit the Learning Center to identify patterns.', 'info')

        # Get step info for logging
        step_name = "Unknown Step"
        if project.template and project.template.workflow_steps and step_index < len(project.template.workflow_steps):
            step_name = project.template.workflow_steps[step_index].get('name', f'Step {step_index + 1}')

        log_research_activity(
            current_user.id,
            'step_completed',
            project_id=project_id,
            duration_minutes=session.duration_minutes if session_id and session else 0,
            details={'step_name': step_name}
        )

        if project.status == 'completed':
            return redirect(url_for('research_workflow.project_summary', project_id=project_id))
        else:
            flash('Step completed! Moving to next step.', 'success')
            return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))

    except Exception as e:
        db.session.rollback()
        flash(f'Error completing step: {str(e)}', 'error')
        return redirect(request.referrer)


@research_workflow_bp.route('/projects/<int:project_id>/mark-too-hard', methods=['GET', 'POST'])
@login_required
def mark_too_hard(project_id):
    """Mark a research project as too hard (abandon mid-research)"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    if request.method == 'GET':
        # Show the mark as too hard form
        # Get user's sectors for autocomplete
        user_sectors = SectorService.get_user_sectors_list(current_user.id, include_inactive=False)

        return render_template('mark_too_hard.html',
                             title=f"Mark as Too Hard: {project.company.name if project.company else project.project_name}",
                             project=project,
                             user_sectors=user_sectors)

    # POST - Process the form submission
    too_hard_reason = request.form.get('too_hard_reason')
    within_coc = request.form.get('within_circle_of_competence')
    too_hard_notes = request.form.get('too_hard_notes', '').strip()
    sector_action = request.form.get('sector_action')
    sector_id = request.form.get('sector_id', type=int)
    new_sector_name = request.form.get('new_sector_name', '').strip()

    # Validation
    if not too_hard_reason:
        flash('Please select a reason for marking this as too hard', 'error')
        return redirect(request.referrer)

    if not within_coc:
        flash('Please indicate if this is within your circle of competence', 'error')
        return redirect(request.referrer)

    try:
        # Update project - mark as pass (too hard = a type of pass decision)
        project.status = 'completed'
        project.decision = 'pass'
        project.decision_date = now_utc()
        project.too_hard_reason = too_hard_reason
        project.within_circle_of_competence = within_coc
        project.too_hard_notes = too_hard_notes
        project.abandoned_at = now_utc()  # Keep for backwards compatibility / timing

        # Handle sector assignment
        if sector_action == 'existing' and sector_id:
            project.sector_id = sector_id
            # Also update company sector if not set
            if project.company and not project.company.sector_id:
                project.company.sector_id = sector_id

        elif sector_action == 'new' and new_sector_name:
            # Create or find sector
            sector = SectorService.find_or_create_sector(
                current_user.id,
                new_sector_name,
                auto_create=True
            )
            project.sector_id = sector.id
            # Also update company sector if not set
            if project.company and not project.company.sector_id:
                project.company.sector_id = sector.id

        db.session.commit()

        log_research_activity(
            current_user.id,
            'project_passed',
            company_id=project.company_id,
            project_id=project.id,
            details={
                'reason': too_hard_reason,
                'within_coc': within_coc,
                'hours_spent': project.total_hours_spent,
                'pass_type': 'mid_research'
            }
        )

        flash(f'Research project marked as too hard. Time invested: {project.total_hours_spent:.1f} hours', 'info')
        return redirect(url_for('research_workflow.my_projects'))

    except Exception as e:
        db.session.rollback()
        logger.error(f'Error marking project as too hard: {str(e)}')
        flash(f'Error marking project as too hard: {str(e)}', 'error')
        return redirect(request.referrer)


@research_workflow_bp.route('/projects/<int:project_id>/complete-research-step/<int:step_index>')
@login_required
def complete_research_step(project_id, step_index):
    """Complete a checklist step when returning from research session"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    try:
        # Mark step as complete
        if not project.completed_steps:
            project.completed_steps = []

        if step_index not in project.completed_steps:
            project.completed_steps = project.completed_steps + [step_index]

        # Save step notes - collect actual research data
        if not project.step_notes:
            project.step_notes = {}

        # Try to collect actual research session data
        research_session_data = collect_research_session_summary(project, step_index)
        project.step_notes[str(step_index)] = research_session_data
        # Explicitly mark the JSON field as modified for SQLAlchemy
        flag_modified(project, 'step_notes')

        # Move to next step if not at the end
        if step_index + 1 < len(project.template.workflow_steps):
            project.current_step_index = step_index + 1
        else:
            project.status = 'completed'
            project.completed_at = now_utc()

        db.session.commit()

        # Clear research context since we're done with this step
        flask_session.pop('research_context', None)

        if project.status == 'completed':
            flash('Research project completed! Review your findings.', 'success')
            return redirect(url_for('research_workflow.project_summary', project_id=project_id))
        else:
            flash('Research step completed! Moving to next step.', 'success')
            return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))

    except Exception as e:
        db.session.rollback()
        flash(f'Error completing research step: {str(e)}', 'error')
        return redirect(request.referrer)


@research_workflow_bp.route('/projects/<int:project_id>/skip-step/<int:step_index>', methods=['POST'])
@login_required
def skip_step(project_id, step_index):
    """Skip a non-critical step in the workflow"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    step = project.template.get_step(step_index)
    if not step:
        return jsonify({'error': 'Invalid step'}), 400

    # Check if step is required/critical
    if step.get('required', False):
        return jsonify({'error': 'Cannot skip required steps'}), 400

    # Mark step as completed with a note that it was skipped
    if step_index not in project.completed_steps:
        project.completed_steps = project.completed_steps + [step_index]

    if not project.step_notes:
        project.step_notes = {}
    project.step_notes[str(step_index)] = "[SKIPPED]"

    # Move to next step
    if step_index + 1 < len(project.template.workflow_steps):
        project.current_step_index = step_index + 1
    else:
        project.status = 'completed'
        project.completed_at = now_utc()

    project.last_worked_at = now_utc()

    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Step skipped'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@research_workflow_bp.route('/projects/<int:project_id>/update-step-checklist/<int:step_index>', methods=['POST'])
@login_required
def update_step_checklist(project_id, step_index):
    """Update the checklist for a specific step (with option to update template)"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    checklist_id = request.form.get('checklist_id', type=int)
    update_template = request.form.get('update_template') == 'yes'

    if not checklist_id:
        flash('Please select a checklist', 'error')
        return redirect(url_for('research_workflow.execute_step', project_id=project_id, step_index=step_index))

    # Verify checklist exists and belongs to user
    checklist = Checklist.query.get(checklist_id)
    if not checklist or checklist.user_id != current_user.id:
        flash('Invalid checklist selection', 'error')
        return redirect(url_for('research_workflow.execute_step', project_id=project_id, step_index=step_index))

    # Check if there are other active projects using this template
    other_active_projects = ResearchProject.query.filter(
        ResearchProject.template_id == project.template_id,
        ResearchProject.id != project_id,
        ResearchProject.status.in_(['active', 'paused'])
    ).count()

    # If user hasn't made a choice yet and there are no other active projects, ask
    if 'update_template' not in request.form and other_active_projects == 0:
        # Show confirmation modal
        return render_template('confirm_checklist_update.html',
                             title="Update Template?",
                             project=project,
                             step_index=step_index,
                             checklist=checklist,
                             checklist_id=checklist_id)

    # Update the project's step configuration (always)
    # We need to override the step config for this specific project
    if not hasattr(project, 'step_overrides') or not project.step_overrides:
        project.step_overrides = {}

    project.step_overrides[str(step_index)] = {
        'checklist_id': checklist_id
    }
    flag_modified(project, 'step_overrides')

    # Update template if requested and safe to do so
    if update_template and other_active_projects == 0:
        template = project.template
        if template and template.workflow_steps:
            template.workflow_steps[step_index]['config']['checklist_id'] = checklist_id
            flag_modified(template, 'workflow_steps')
            flash(f'Checklist updated for this project and template "{template.name}"', 'success')
    else:
        flash(f'Checklist updated for this project only', 'success')

    try:
        db.session.commit()
        # Now redirect to execute the step with the new checklist
        return redirect(url_for('research_workflow.execute_step', project_id=project_id, step_index=step_index))
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating checklist: {str(e)}', 'error')
        return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))


@research_workflow_bp.route('/projects/<int:project_id>/steps/<int:step_index>/return-from-checklist')
@login_required
def return_from_checklist(project_id, step_index):
    """Handle return from legacy checklist execution to research workflow"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    # Get the research context from session
    research_context = flask_session.pop('research_context', None)
    if research_context and research_context.get('project_id') == project_id:

        # Mark the step as completed (similar to complete_step route)
        if project.template and project.template.workflow_steps and step_index < len(project.template.workflow_steps):
            # Mark step as complete
            if not project.completed_steps:
                project.completed_steps = []

            if step_index not in project.completed_steps:
                project.completed_steps = project.completed_steps + [step_index]

            # Save step notes
            if not project.step_notes:
                project.step_notes = {}
            project.step_notes[str(step_index)] = 'Completed via legacy investment checklist'

            # Update last worked timestamp
            project.last_worked_at = now_utc()

            try:
                db.session.commit()
                flash('Investment checklist step completed successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating project progress: {str(e)}', 'error')

        # Redirect back to project dashboard
        return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))
    else:
        # No valid research context, just go to project dashboard
        flash('Returned from checklist execution', 'info')
        return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))
