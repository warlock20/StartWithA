from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required
from app import db
from app.models import (ResearchTemplate, ResearchProject, WorkSession, 
                       TemplateStep, Company, Checklist, IdeaPipeline,
                       ResearchSession, ChecklistItem, ResearchAnswer)
from app.research_workflow import research_workflow_bp
from app.analytics.utils import log_research_activity
from datetime import datetime, timedelta
import json

@research_workflow_bp.route('/templates')
@login_required
def template_list():
    """Display all research templates for the current user"""
    templates = current_user.research_templates.order_by(
        ResearchTemplate.is_active.desc(),
        ResearchTemplate.times_used.desc()
    ).all()
    
    # Get statistics for the dashboard
    total_projects = current_user.research_projects.count()
    active_projects = current_user.research_projects.filter_by(status='active').count()
    total_research_hours = db.session.query(
        db.func.sum(ResearchProject.total_hours_spent)
    ).filter_by(user_id=current_user.id).scalar() or 0
    
    return render_template('template_list.html',
                          title="Research Templates",
                          templates=templates,
                          total_projects=total_projects,
                          active_projects=active_projects,
                          total_research_hours=round(total_research_hours, 1))

@research_workflow_bp.route('/templates/create', methods=['GET', 'POST'])
@login_required
def create_template():
    """Create a new research template"""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        investment_style = request.form.get('investment_style')
        
        if not name:
            flash('Template name is required', 'error')
            return redirect(url_for('research_workflow.create_template'))
        
        # Build workflow steps from form data
        workflow_steps = []
        step_names = request.form.getlist('step_name[]')
        step_types = request.form.getlist('step_type[]')
        step_configs = request.form.getlist('step_config[]')
        step_required = request.form.getlist('step_required[]')
        step_estimates = request.form.getlist('step_estimate[]')
        
        for i, step_name in enumerate(step_names):
            if step_name.strip():  # Only add non-empty steps
                step = {
                    'order': i + 1,
                    'name': step_name.strip(),
                    'type': step_types[i] if i < len(step_types) else 'custom',
                    'config': json.loads(step_configs[i]) if i < len(step_configs) and step_configs[i] else {},
                    'required': i in step_required,
                    'estimated_minutes': int(step_estimates[i]) if i < len(step_estimates) and step_estimates[i] else 60
                }
                
                # Add type-specific configuration
                if step['type'] == 'checklist':
                    step['config']['checklist_id'] = request.form.get(f'step_{i}_checklist_id')
                elif step['type'] == 'model':
                    step['config']['model_type'] = request.form.get(f'step_{i}_model_type')
                
                workflow_steps.append(step)
        
        # Create the template
        template = ResearchTemplate(
            author=current_user,
            name=name,
            description=description,
            investment_style=investment_style,
            workflow_steps=workflow_steps
        )
        
        try:
            db.session.add(template)
            db.session.commit()
            flash(f'Research template "{name}" created successfully!', 'success')
            return redirect(url_for('research_workflow.template_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating template: {str(e)}', 'error')
    
    # Get user's checklists for the step configuration
    user_checklists = current_user.checklists.all()
    
    # Define available step types and mental models
    step_types = [
        {'value': 'checklist', 'label': 'Run Checklist', 'icon': '📋'},
        {'value': 'model', 'label': 'Mental Model', 'icon': '🧠'},
        {'value': 'document_review', 'label': 'Document Analysis', 'icon': '📄'},
        {'value': 'valuation', 'label': 'Valuation Work', 'icon': '💰'},
        {'value': 'competitor_analysis', 'label': 'Competitor Analysis', 'icon': '🎯'},
        {'value': 'thesis_writing', 'label': 'Write Investment Thesis', 'icon': '✍️'},
        {'value': 'custom', 'label': 'Custom Task', 'icon': '⚙️'}
    ]
    
    mental_models = [
        'SWOT Analysis',
        'Porter\'s Five Forces',
        'Moat Analysis',
        'Management Quality Assessment',
        'Unit Economics',
        'TAM Analysis',
        'Risk Assessment'
    ]
    
    return render_template('create_template.html',
                          title="Create Research Template",
                          user_checklists=user_checklists,
                          step_types=step_types,
                          mental_models=mental_models)

@research_workflow_bp.route('/projects/start', methods=['POST'])
@login_required
def start_project():
    """Start a new research project using a template"""
    company_id = request.form.get('company_id', type=int)
    template_id = request.form.get('template_id', type=int)
    
    if not company_id or not template_id:
        flash('Company and template are required', 'error')
        return redirect(request.referrer or url_for('companies.list_companies'))
    
    # Verify ownership
    company = Company.query.get_or_404(company_id)
    template = ResearchTemplate.query.get_or_404(template_id)
    
    if company.user_id != current_user.id or template.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('companies.list_companies'))
    
    # Check for existing active project
    existing = ResearchProject.query.filter_by(
        user_id=current_user.id,
        company_id=company_id,
        template_id=template_id,
        status='active'
    ).first()
    
    if existing:
        flash('You already have an active project for this company with this template', 'info')
        return redirect(url_for('research_workflow.project_dashboard', project_id=existing.id))
    
    # Create new project
    project = ResearchProject(
        researcher=current_user,
        company=company,
        template=template,
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
    
    # Update template usage count
    template.times_used += 1
    
    try:
        db.session.add(project)
        db.session.commit()
        log_research_activity(
            current_user.id,
            'research_started',
            company_id=company_id,
            project_id=project.id
        )
        flash(f'Research project started for {company.name}!', 'success')
        return redirect(url_for('research_workflow.project_dashboard', project_id=project.id))
    except Exception as e:
        db.session.rollback()
        flash(f'Error starting project: {str(e)}', 'error')
        return redirect(request.referrer or url_for('companies.list_companies'))

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
    
    return render_template('project_dashboard.html',
                          title=f"Research: {project.project_name}",
                          project=project,
                          recent_sessions=recent_sessions,
                          time_breakdown=time_breakdown,
                          next_steps=next_steps,
                          datetime=datetime)

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
    
    # Start a work session
    session = WorkSession(
        project=project,
        user=current_user,
        step_index=step_index,
        step_name=step['name'],
        start_time=datetime.utcnow()
    )
    db.session.add(session)
    db.session.commit()
    
    # Route to appropriate handler based on step type
    if step['type'] == 'checklist':
        checklist_id = step['config'].get('checklist_id')
        if checklist_id:
            # Create or resume a research session for this checklist
            research_session = ResearchSession.query.filter_by(
                user_id=current_user.id,
                company_id=project.company_id,
                checklist_id=checklist_id
            ).first()
            
            if not research_session:
                research_session = ResearchSession(
                    researcher=current_user,
                    company=project.company,
                    checklist_id=checklist_id,
                    status='in_progress'
                )
                db.session.add(research_session)
                db.session.commit()
            
            # Redirect to the existing research flow
            return redirect(url_for('research.research_step', 
                                  session_id=research_session.id,
                                  item_id=ChecklistItem.query.filter_by(
                                      checklist_id=checklist_id
                                  ).first().id))
    
    elif step['type'] == 'model':
        model_type = step['config'].get('model_type')
        if model_type == 'SWOT Analysis':
            return redirect(url_for('companies.swot_analysis', 
                                  company_id=project.company_id))
        elif model_type == 'Porter\'s Five Forces':
            return redirect(url_for('companies.porters_five_forces_analysis', 
                                  company_id=project.company_id))
    
    # For other step types, show the generic execution interface
    return render_template('execute_step.html',
                          title=f"Execute: {step['name']}",
                          project=project,
                          step=step,
                          step_index=step_index,
                          session=session)

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
            session.end_time = datetime.utcnow()
            session.duration_minutes = int(
                (session.end_time - session.start_time).total_seconds() / 60
            )
            session.notes = notes
            
            # Update project time tracking
            if not project.time_per_step:
                project.time_per_step = {}
            
            current_time = project.time_per_step.get(str(step_index), 0)
            project.time_per_step[str(step_index)] = current_time + session.duration_minutes
            project.total_hours_spent += session.duration_minutes / 60
    
    # Mark step as complete
    if step_index not in project.completed_steps:
        project.completed_steps = project.completed_steps + [step_index]
    
    # Save step notes
    if not project.step_notes:
        project.step_notes = {}
    project.step_notes[str(step_index)] = notes
    
    # Update project progress
    project.last_worked_at = datetime.utcnow()
    
    # Move to next step or complete project
    if step_index + 1 < len(project.template.workflow_steps):
        project.current_step_index = step_index + 1
    else:
        project.status = 'completed'
        project.completed_at = datetime.utcnow()
        flash('Research project completed! Time to make your investment decision.', 'success')
    
    try:
        db.session.commit()
        log_research_activity(
            current_user.id,
            'step_completed',
            project_id=project_id,
            duration_minutes=session.duration_minutes,
            details={'step_name': step['name']}
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
                'step_name': step['name'],
                'notes': notes
            })
    
    return render_template('project_summary.html',
                          title=f"Summary: {project.project_name}",
                          project=project,
                          all_notes=all_notes)

@research_workflow_bp.route('/projects/<int:project_id>/decision', methods=['POST'])
@login_required
def save_decision(project_id):
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    # --- Get form data ---
    decision = request.form.get('decision')
    project.decision = decision # Save the decision to the project
    project.decision_confidence = request.form.get('confidence', type=int)
    project.decision_notes = request.form.get('decision_notes')
    project.decision_date = datetime.utcnow()

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

    # --- NEW LOGIC TO UNIFY WATCHLISTS ---
    flash_message = 'Investment decision saved!' # Default message

    if decision == 'watchlist':
        company_to_watch = project.company
        if company_to_watch not in current_user.favorites:
            current_user.favorites.append(company_to_watch)
            # Update flash message to inform the user
            flash_message = f'Decision saved. "{company_to_watch.name}" has been added to your Favorites/Watchlist.'

    try:
        db.session.commit()
        flash(flash_message, 'success') # Use the dynamic flash message

        if project.decision == 'invest':
            # Redirect to portfolio or next steps
            return redirect(url_for('companies.list_companies'))
        else:
            # Back to project list
            return redirect(url_for('research_workflow.my_projects'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error saving decision: {str(e)}', 'error')
        return redirect(request.referrer)

@research_workflow_bp.route('/my-projects')
@login_required
def my_projects():
    """Show all research projects for the current user"""
    # Get projects grouped by status
    active_projects = current_user.research_projects.filter_by(status='active')\
                                                    .order_by(ResearchProject.last_worked_at.desc()).all()
    
    paused_projects = current_user.research_projects.filter_by(status='paused')\
                                                    .order_by(ResearchProject.created_at.desc()).all()
    
    completed_projects = current_user.research_projects.filter_by(status='completed')\
                                                      .order_by(ResearchProject.completed_at.desc()).limit(10).all()
    
    # Flag overdue projects
    overdue_projects = [p for p in active_projects if p.is_overdue]
    
    # Calculate total time invested
    total_time_invested = sum(p.total_hours_spent for p in current_user.research_projects.all())
    
    # Success metrics
    total_decisions = current_user.research_projects.filter(
        ResearchProject.decision.isnot(None)
    ).count()
    
    invest_decisions = current_user.research_projects.filter_by(decision='invest').count()
    pass_decisions = current_user.research_projects.filter_by(decision='pass').count()
    
    return render_template('my_projects.html',
                          title="My Research Projects",
                          active_projects=active_projects,
                          paused_projects=paused_projects,
                          completed_projects=completed_projects,
                          overdue_projects=overdue_projects,
                          total_time_invested=round(total_time_invested, 1),
                          total_decisions=total_decisions,
                          invest_decisions=invest_decisions,
                          pass_decisions=pass_decisions)

@research_workflow_bp.route('/projects/<int:project_id>/pause', methods=['POST'])
@login_required
def pause_project(project_id):
    """Pause an active research project"""
    project = ResearchProject.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))
    
    project.status = 'paused'
    project.last_worked_at = datetime.utcnow()
    
    try:
        db.session.commit()
        flash(f'Project "{project.project_name}" paused', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error pausing project: {str(e)}', 'error')
    
    return redirect(url_for('research_workflow.my_projects'))

@research_workflow_bp.route('/projects/<int:project_id>/resume', methods=['POST'])
@login_required
def resume_project(project_id):
    """Resume a paused research project"""
    project = ResearchProject.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))
    
    project.status = 'active'
    project.last_worked_at = datetime.utcnow()
    
    try:
        db.session.commit()
        flash(f'Project "{project.project_name}" resumed', 'success')
        return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))
    except Exception as e:
        db.session.rollback()
        flash(f'Error resuming project: {str(e)}', 'error')
        return redirect(url_for('research_workflow.my_projects'))

@research_workflow_bp.route('/templates/<int:template_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_template(template_id):
    """Edit an existing research template"""
    template = ResearchTemplate.query.get_or_404(template_id)
    
    if template.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.template_list'))
    
    if request.method == 'POST':
        template.name = request.form.get('name', template.name)
        template.description = request.form.get('description')
        template.investment_style = request.form.get('investment_style')
        
        # Rebuild workflow steps
        workflow_steps = []
        step_names = request.form.getlist('step_name[]')
        step_types = request.form.getlist('step_type[]')
        step_estimates = request.form.getlist('step_estimate[]')
        
        for i, step_name in enumerate(step_names):
            if step_name.strip():
                step = {
                    'order': i + 1,
                    'name': step_name.strip(),
                    'type': step_types[i] if i < len(step_types) else 'custom',
                    'estimated_minutes': int(step_estimates[i]) if i < len(step_estimates) and step_estimates[i] else 60,
                    'config': {}
                }
                workflow_steps.append(step)
        
        template.workflow_steps = workflow_steps
        template.updated_at = datetime.utcnow()
        
        try:
            db.session.commit()
            flash('Template updated successfully!', 'success')
            return redirect(url_for('research_workflow.template_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating template: {str(e)}', 'error')
    
    return render_template('edit_template.html',
                          title=f"Edit Template: {template.name}",
                          template=template)

@research_workflow_bp.route('/templates/<int:template_id>/delete', methods=['POST'])
@login_required
def delete_template(template_id):
    """Delete a research template"""
    template = ResearchTemplate.query.get_or_404(template_id)
    
    if template.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.template_list'))
    
    # Check if template has active projects
    active_projects = ResearchProject.query.filter_by(
        template_id=template_id,
        status='active'
    ).count()
    
    if active_projects > 0:
        flash('Cannot delete template with active projects', 'error')
        return redirect(url_for('research_workflow.template_list'))
    
    try:
        db.session.delete(template)
        db.session.commit()
        flash(f'Template "{template.name}" deleted', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting template: {str(e)}', 'error')
    
    return redirect(url_for('research_workflow.template_list'))

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
    project.last_worked_at = datetime.utcnow()
    
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
        return jsonify({'error': 'Access denied'}), 403
    
    finding_type = request.form.get('finding_type')  # 'green_flag' or 'red_flag'
    finding_text = request.form.get('finding_text', '').strip()
    
    if not finding_text:
        return jsonify({'error': 'Finding text is required'}), 400
    
    if finding_type == 'green_flag':
        if not project.green_flags:
            project.green_flags = []
        project.green_flags = project.green_flags + [finding_text]
    elif finding_type == 'red_flag':
        if not project.red_flags:
            project.red_flags = []
        project.red_flags = project.red_flags + [finding_text]
    else:
        return jsonify({'error': 'Invalid finding type'}), 400
    
    project.last_worked_at = datetime.utcnow()
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Finding added'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@research_workflow_bp.route('/projects/<int:project_id>/abandon', methods=['POST'])
@login_required
def abandon_project(project_id):
    """Abandon a research project"""
    project = ResearchProject.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))
    
    project.status = 'abandoned'
    project.completed_at = datetime.utcnow()
    
    # Optional: Record reason for abandonment
    reason = request.form.get('reason', '')
    if reason:
        if not project.decision_notes:
            project.decision_notes = ''
        project.decision_notes += f"\n\nAbandoned: {reason}"
    
    try:
        db.session.commit()
        flash(f'Project "{project.project_name}" has been abandoned', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error abandoning project: {str(e)}', 'error')
    
    return redirect(url_for('research_workflow.my_projects'))

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
        project.completed_at = datetime.utcnow()
    
    project.last_worked_at = datetime.utcnow()
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Step skipped'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@research_workflow_bp.route('/quick-start', methods=['GET'])
@login_required
def quick_start_guide():
    """Show a quick start guide for new users"""
    # Get sample templates or create starter templates
    starter_templates = ResearchTemplate.query.filter_by(
        user_id=current_user.id
    ).limit(3).all()
    
    if not starter_templates:
        # Optionally create a default template for new users
        default_template = create_default_template_for_user(current_user)
        if default_template:
            starter_templates = [default_template]
    
    return render_template('quick_start.html',
                          title="Quick Start Guide",
                          starter_templates=starter_templates)

def create_default_template_for_user(user):
    """Helper function to create a default research template for new users"""
    default_steps = [
        {'order': 1, 'name': 'Initial Financial Screening', 'type': 'checklist', 
         'config': {}, 'required': True, 'estimated_minutes': 30},
        {'order': 2, 'name': 'Business Model Analysis', 'type': 'custom', 
         'config': {}, 'required': True, 'estimated_minutes': 60},
        {'order': 3, 'name': 'Management Assessment', 'type': 'custom', 
         'config': {}, 'required': False, 'estimated_minutes': 45},
        {'order': 4, 'name': 'Competitive Position Review', 'type': 'competitor_analysis', 
         'config': {}, 'required': True, 'estimated_minutes': 90},
        {'order': 5, 'name': 'Valuation Analysis', 'type': 'valuation', 
         'config': {}, 'required': True, 'estimated_minutes': 120},
        {'order': 6, 'name': 'Risk Assessment', 'type': 'custom', 
         'config': {}, 'required': True, 'estimated_minutes': 60},
        {'order': 7, 'name': 'Investment Thesis', 'type': 'thesis_writing', 
         'config': {}, 'required': True, 'estimated_minutes': 45}
    ]
    
    template = ResearchTemplate(
        author=user,
        name="Fundamental Analysis Template",
        description="A comprehensive template for fundamental stock analysis covering financials, business quality, and valuation",
        investment_style="value",
        workflow_steps=default_steps,
        is_active=True
    )
    
    try:
        db.session.add(template)
        db.session.commit()
        return template
    except:
        db.session.rollback()
        return None