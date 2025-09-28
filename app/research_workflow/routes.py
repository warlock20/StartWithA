from flask import render_template, request, redirect, url_for, flash, jsonify, current_app, session as flask_session
from flask_login import current_user, login_required
from app import db
from app.models import (ResearchTemplate, ResearchProject, WorkSession,
                       ResearchLog, Company, Checklist, KillChecklist, IdeaPipeline, CompanyDocument, 
                       DecisionJournal, JournalEntry, ResearchSession, ResearchAnswer)
from app.research_workflow import research_workflow_bp
from app.analytics.utils import log_research_activity
from datetime import datetime, timedelta, timezone
from app.utils.time_utils import now_utc, ensure_timezone_aware, calculate_duration_minutes, format_for_javascript
from app.services.llm_service import generate_ai_content
from app.research.routes import get_all_ordered_items_for_checklist
from app.services.adaptive_template_service import (
    suggest_template_adaptations,
    apply_template_adaptations,
    adaptive_template_service
)

import json
import logging

logger = logging.getLogger(__name__)

@research_workflow_bp.route('/api/server-time')
@login_required
def get_server_time():
    """API endpoint to get current server time for timer synchronization"""
    return jsonify({
        'server_time': now_utc().isoformat(),
        'timezone': 'UTC'
    })

def collect_research_session_summary(project, step_index):
    """
    Collect and summarize the actual research data from the completed research session
    """
    try:
        # Find the most recent research session for this project's company

        if not project.company_id:
            return "Completed research checklist evaluation (no company data)"

        # Get the most recent research session for this company (check all statuses first)
        all_sessions = ResearchSession.query.filter_by(
            user_id=current_user.id,
            company_id=project.company_id
        ).order_by(ResearchSession.start_date.desc()).all()


        # Get the most recent research session for this company (try 'completed' first)
        recent_session = ResearchSession.query.filter_by(
            user_id=current_user.id,
            company_id=project.company_id,
            status='completed'
        ).order_by(ResearchSession.start_date.desc()).first()

        # If no completed session, try any recent session
        if not recent_session and all_sessions:
            recent_session = all_sessions[0]

        if not recent_session:
            return "Completed research checklist evaluation (no research session found)"

        # Collect all research answers from the session
        research_answers = ResearchAnswer.query.filter_by(
            research_session_id=recent_session.id
        ).all()

        if not research_answers:
            return f"Completed research evaluation using {recent_session.checklist.name} (no answers recorded)"

        # Build summary from the research answers
        summary_parts = [
            f"**Research Summary: {recent_session.checklist.name}**",
            f"Company: {project.company.name} ({project.company.ticker_symbol})",
            f"Completed: {recent_session.start_date.strftime('%Y-%m-%d')}",
            "",
            "**Key Research Findings:**"
        ]

        # Categorize answers by satisfaction status
        satisfied_items = []
        not_satisfied_items = []
        needs_attention_items = []
        informational_items = []

        for answer in research_answers:
            item_text = answer.item.text[:100] + "..." if len(answer.item.text) > 100 else answer.item.text

            if answer.satisfaction_status == 'satisfied':
                satisfied_items.append(f"✅ {item_text}")
            elif answer.satisfaction_status == 'not_satisfied':
                not_satisfied_items.append(f"❌ {item_text}")
            elif answer.satisfaction_status == 'needs_attention':
                needs_attention_items.append(f"⚠️ {item_text}")
            else:
                informational_items.append(f"ℹ️ {item_text}")

        # Add categorized findings
        if satisfied_items:
            summary_parts.append("\n**Positive Findings:**")
            summary_parts.extend(satisfied_items[:5])  # Limit to top 5

        if not_satisfied_items:
            summary_parts.append("\n**Concerns:**")
            summary_parts.extend(not_satisfied_items[:5])

        if needs_attention_items:
            summary_parts.append("\n**Needs Attention:**")
            summary_parts.extend(needs_attention_items[:5])

        # Add summary statistics
        total_items = len(research_answers)
        satisfied_count = len(satisfied_items)
        pass_rate = round((satisfied_count / total_items) * 100) if total_items > 0 else 0

        summary_parts.extend([
            "",
            f"**Summary Stats:**",
            f"- Total Items Evaluated: {total_items}",
            f"- Satisfied: {satisfied_count} ({pass_rate}%)",
            f"- Concerns: {len(not_satisfied_items)}",
            f"- Needs Attention: {len(needs_attention_items)}"
        ])

        final_summary = "\n".join(summary_parts)
        return final_summary

    except Exception as e:
        import traceback
        print(f"ERROR in collect_research_session_summary: {e}")
        print(f"TRACEBACK: {traceback.format_exc()}")
        return f"Completed research checklist evaluation (error collecting details: {str(e)})"

@research_workflow_bp.route('/intelligent-routing')
@login_required
def intelligent_routing():
    """Intelligent routing based on existing data and project status"""
    company_id = request.args.get('company_id', type=int)
    source = request.args.get('source', 'unknown')

    if not company_id:
        flash('Company ID is required for intelligent routing', 'error')
        return redirect(url_for('dashboard.main'))

    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard.main'))

    # Check for existing active projects for this company
    active_projects = ResearchProject.query.filter_by(
        user_id=current_user.id,
        company_id=company_id,
        status='active'
    ).all()

    # Check for paused projects for this company
    paused_projects = ResearchProject.query.filter_by(
        user_id=current_user.id,
        company_id=company_id,
        status='paused'
    ).all()

    # Check for completed projects for this company
    completed_projects = ResearchProject.query.filter_by(
        user_id=current_user.id,
        company_id=company_id,
        status='completed'
    ).all()

    # Check for existing financial data
    has_financial_data = company.company_documents.filter_by(doc_type='financial_data').first() is not None

    # Intelligent routing logic
    if active_projects:
        # User has active projects - redirect to most recent one
        latest_project = max(active_projects, key=lambda p: p.created_at)
        flash(f'You have an active research project for {company.name}. Redirecting to project dashboard.', 'info')
        return redirect(url_for('research_workflow.project_dashboard', project_id=latest_project.id))

    elif paused_projects:
        # User has paused projects - offer to resume
        latest_paused = max(paused_projects, key=lambda p: p.created_at)
        flash(f'You have a paused research project for {company.name}. Consider resuming it or start a new one.', 'warning')
        return redirect(url_for('research_workflow.project_dashboard', project_id=latest_paused.id))

    elif completed_projects:
        # User has completed projects - suggest new research angles
        flash(f'You\'ve completed research on {company.name}. Consider new research angles or templates.', 'info')
        return redirect(url_for('research_workflow.template_list', company_id=company_id, suggested=True))

    else:
        # No existing research - start fresh with template selection
        if source == 'idea_promotion':
            flash(f'Company created! Now choose a research template to begin systematic analysis of {company.name}.', 'success')
        return redirect(url_for('research_workflow.template_list', company_id=company_id, new_company=True))

@research_workflow_bp.route('/templates')
@login_required
def template_list():
    """Display all research templates for the current user with intelligent context"""
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

    # Check for intelligent routing context
    company_id = request.args.get('company_id', type=int)
    suggested = request.args.get('suggested', default=False, type=bool)
    new_company = request.args.get('new_company', default=False, type=bool)

    context = {}
    if company_id:
        company = Company.query.get(company_id)
        if company and company.user_id == current_user.id:
            context['company'] = company
            context['suggested'] = suggested
            context['new_company'] = new_company

            # Add previous template usage for this company
            if not new_company:
                used_templates = ResearchProject.query.filter_by(
                    user_id=current_user.id,
                    company_id=company_id
                ).join(ResearchTemplate).with_entities(ResearchTemplate.id, ResearchTemplate.name).distinct().all()
                context['used_templates'] = used_templates

    return render_template('template_list.html',
                          title="Research Templates",
                          templates=templates,
                          total_projects=total_projects,
                          active_projects=active_projects,
                          total_research_hours=round(total_research_hours, 1),
                          context=context)

@research_workflow_bp.route('/templates/create', methods=['GET', 'POST'])
@login_required
def create_template():
    """Create a new research template"""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        investment_style = request.form.get('investment_style')
        custom_investment_style = request.form.get('custom_investment_style')
        research_subject_type = request.form.get('research_subject_type')
        
        # Use custom investment style if selected
        if investment_style == 'custom' and custom_investment_style:
            investment_style = custom_investment_style.strip()
        
        # Validate research subject type
        if not research_subject_type:
            flash('Research subject type must be selected', 'error')
            return redirect(url_for('research_workflow.create_template'))
        
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
                elif step['type'] == 'kill_checklist_reference':
                    step['config']['kill_checklist_id'] = request.form.get(f'step_{i}_kill_checklist_id')
                elif step['type'] == 'model':
                    step['config']['model_type'] = request.form.get(f'step_{i}_model_type')
                
                workflow_steps.append(step)
        
        # Create the template
        template = ResearchTemplate(
            author=current_user,
            name=name,
            description=description,
            investment_style=investment_style,
            research_subject_types=[research_subject_type],  # Store as single-item list for consistency
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
    
    # Get user's checklists and kill checklists for the step configuration
    user_checklists = [{'id': cl.id, 'name': cl.name} for cl in current_user.checklists.all()]
    user_kill_checklists = [{'id': kc.id, 'name': kc.name} for kc in current_user.kill_checklists.all()]
    
    # Define available step types and mental models
    step_types = [
        {'value': 'checklist', 'label': 'Investment Checklist', 'icon': '📋'},
        {'value': 'kill_checklist_reference', 'label': 'Kill Checklist (Screening)', 'icon': '⚡'},
        {'value': 'model', 'label': 'Mental Model', 'icon': '🧠'},
        {'value': 'document_review', 'label': 'Document Analysis', 'icon': '📄'},
        {'value': 'valuation', 'label': 'Valuation Work', 'icon': '💰'},
        {'value': 'competitor_analysis', 'label': 'Competitor Analysis', 'icon': '🎯'},
        {'value': 'thesis_writing', 'label': 'Write Investment Thesis', 'icon': '✍️'},
        {'value': 'learning_overview', 'label': 'Learning Overview', 'icon': '📚'},
        {'value': 'concept_study', 'label': 'Concept Study', 'icon': '🎓'},
        {'value': 'industry_deep_dive', 'label': 'Industry Deep Dive', 'icon': '🏭'},
        {'value': 'business_model_analysis', 'label': 'Business Model Analysis', 'icon': '💼'},
        {'value': 'case_study', 'label': 'Case Study', 'icon': '📖'},
        {'value': 'custom', 'label': 'Custom Task', 'icon': '⚙️'}
    ]
    
    mental_models = [
        'SWOT Analysis',
        'Porter\'s Five Forces'
    ]
    
    return render_template('create_template.html',
                          title="Create Research Template",
                          user_checklists=user_checklists,
                          user_kill_checklists=user_kill_checklists,
                          step_types=step_types,
                          mental_models=mental_models)

@research_workflow_bp.route('/templates/<int:template_id>/view')
@login_required
def view_template(template_id):
    """View/preview a research template to visualize workflow steps"""
    template = ResearchTemplate.query.get_or_404(template_id)
    
    if template.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.template_list'))
    
    # Calculate total estimated time
    total_minutes = 0
    for step in template.workflow_steps:
        total_minutes += step.get('estimated_minutes', 60)
    
    # Group steps by type for analysis
    step_types_count = {}
    for step in template.workflow_steps:
        step_type = step.get('type', 'custom')
        step_types_count[step_type] = step_types_count.get(step_type, 0) + 1
    
    # Get usage statistics
    active_projects = ResearchProject.query.filter_by(
        template_id=template.id, 
        status='active'
    ).count()
    
    completed_projects = ResearchProject.query.filter_by(
        template_id=template.id, 
        status='completed'
    ).all()
    
    return render_template('view_template.html',
                          title=f"Template: {template.name}",
                          template=template,
                          total_minutes=total_minutes,
                          total_hours=round(total_minutes / 60, 1),
                          step_types_count=step_types_count,
                          active_projects=active_projects,
                          completed_projects=completed_projects)

@research_workflow_bp.route('/projects/start', methods=['POST'])
@login_required
def start_project():
    """Start a new research project using a template"""
    template_id = request.form.get('template_id', type=int)
    subject_type = request.form.get('subject_type', 'company')
    subject_name = request.form.get('subject_name', '')
    company_id = request.form.get('company_id', type=int)
    
    # Validate inputs based on subject type
    if not template_id:
        flash('Template selection is required', 'error')
        return redirect(request.referrer or url_for('research_workflow.template_list'))
    
    if subject_type == 'company' and not company_id:
        flash('Company selection is required for company research', 'error')
        return redirect(request.referrer or url_for('research_workflow.template_list'))
    elif subject_type != 'company' and not subject_name:
        flash('Research subject name is required', 'error')
        return redirect(request.referrer or url_for('research_workflow.template_list'))
    
    # Verify template ownership
    template = ResearchTemplate.query.get_or_404(template_id)
    if template.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.template_list'))
    
    # Handle company-specific logic
    company = None
    if subject_type == 'company':
        company = Company.query.get_or_404(company_id)
        if company.user_id != current_user.id:
            flash('Access denied', 'error')
            return redirect(url_for('research_workflow.template_list'))

        subject_name = company.name
    
    # ENFORCE CONSTRAINT: ONE RESEARCH PROJECT PER COMPANY (regardless of template)
    if subject_type == 'company' and company_id:
        existing_project = ResearchProject.query.filter_by(
            user_id=current_user.id,
            company_id=company_id
        ).filter(
            ResearchProject.status.in_(['active', 'paused'])
        ).first()

        if existing_project:
            if existing_project.status == 'active':
                flash(f'You already have an active research project for {subject_name}. Only one project per company is allowed.', 'error')
                return redirect(url_for('research_workflow.project_dashboard', project_id=existing_project.id))
            elif existing_project.status == 'paused':
                flash(f'You have a paused research project for {subject_name}. Resume it or delete it to start a new one.', 'warning')
                return redirect(url_for('research_workflow.project_dashboard', project_id=existing_project.id))

    # Check for existing project with same template (for non-company subjects)
    if subject_type != 'company':
        existing = ResearchProject.query.filter_by(
            user_id=current_user.id,
            template_id=template_id,
            research_subject_type=subject_type,
            research_subject_name=subject_name
        ).first()
        if existing and existing.status in ['active', 'paused']:
            flash(f'You already have a project for {subject_name} with this template', 'info')
            return redirect(url_for('research_workflow.project_dashboard', project_id=existing.id))
    
    # Create new project
    project = ResearchProject(
        researcher=current_user,
        template=template,
        research_subject_type=subject_type,
        research_subject_name=subject_name,
        company=company,
        project_name=f"{subject_name} - {template.name}",
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
            company_id=company.id if company else None,
            project_id=project.id
        )
        flash(f'Research project started for {subject_name}!', 'success')
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
        latest_research_session = ResearchSession.query.filter_by(
            company_id=project.company_id,
            user_id=current_user.id,
            status='completed'
        ).order_by(ResearchSession.start_date.desc()).first()

    # Calculate days since last work using proper timezone handling
    days_since_last_work = None
    if project.last_worked_at:
        last_worked_aware = ensure_timezone_aware(project.last_worked_at)
        current_time = now_utc()
        days_since_last_work = (current_time - last_worked_aware).days

    return render_template('project_dashboard.html',
                          title=f"Research: {project.project_name}",
                          project=project,
                          recent_sessions=recent_sessions,
                          time_breakdown=time_breakdown,
                          next_steps=next_steps,
                          latest_research_session=latest_research_session,
                          days_since_last_work=days_since_last_work)

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
                existing_research_session = ResearchSession.query.filter_by(
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
                                answer_exists = ResearchAnswer.query.filter_by(
                                    research_session_id=existing_research_session.id,
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
                                                  session_id=existing_research_session.id,
                                                  item_id=redirect_to_item_id))
                        else:
                            flash('Investment checklist has no items to evaluate', 'warning')
                            return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))

                    elif existing_research_session.status == 'completed':
                        flash('Investment checklist research already completed. Viewing summary.', 'info')
                        return redirect(url_for('research.view_checklist_session_summary',
                                              session_id=existing_research_session.id))
                else:
                    # Create new research session
                    new_research_session = ResearchSession(
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
                                                  session_id=new_research_session.id,
                                                  item_id=all_items[0].id))
                        else:
                            flash('Investment checklist has no items to evaluate', 'warning')
                            return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))

                    except Exception as e:
                        db.session.rollback()
                        flash(f'Error starting research session: {str(e)}', 'error')
                        return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))
            else:
                flash('Investment checklist not found or access denied', 'error')
                return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))
        else:
            flash('No investment checklist configured for this step', 'warning')
            return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))
    
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
                                  company_id=project.company_id))
        elif model_type == 'Porter\'s Five Forces':
            return redirect(url_for('companies.porters_five_forces_analysis', 
                                  company_id=project.company_id))
    
    # For other step types, show the generic execution interface
    # Format session start time for JavaScript timer
    session_start_js = format_for_javascript(session.start_time)

    return render_template('execute_step.html',
                          title=f"Execute: {step['name']}",
                          project=project,
                          step=step,
                          step_index=step_index,
                          session=session,
                          session_start_js=session_start_js)

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
        from sqlalchemy.orm.attributes import flag_modified
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

    # --- NEW LOGIC TO UNIFY WATCHLISTS ---
    flash_message = 'Decision saved!' # Default message

    if decision == 'watchlist' and project.research_subject_type == 'company' and project.company:
        company_to_watch = project.company
        if company_to_watch not in current_user.favorites:
            current_user.favorites.append(company_to_watch)
            # Update flash message to inform the user
            flash_message = f'Decision saved. "{company_to_watch.name}" has been added to your Favorites/Watchlist.'
    elif decision == 'watchlist':
        # For non-company projects, just save the decision without adding to favorites
        if project.research_subject_type == 'sector':
            flash_message = f'Sector assessment saved. "{project.research_subject_name}" marked for watching.'
        else:
            flash_message = f'Research decision saved. "{project.research_subject_name}" marked for watching.'

    try:
        db.session.commit()
        flash(flash_message, 'success') # Use the dynamic flash message

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

    # Legacy research sessions removed - now handled through research workflow system

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
    project.last_worked_at = now_utc()
    
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
    project.last_worked_at = now_utc()
    
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
                
                # Add type-specific configuration
                if step['type'] == 'checklist':
                    step['config']['checklist_id'] = request.form.get(f'step_{i}_checklist_id')
                elif step['type'] == 'kill_checklist_reference':
                    step['config']['kill_checklist_id'] = request.form.get(f'step_{i}_kill_checklist_id')
                elif step['type'] == 'model':
                    step['config']['model_type'] = request.form.get(f'step_{i}_model_type')
                
                workflow_steps.append(step)
        
        template.workflow_steps = workflow_steps
        template.updated_at = now_utc()
        
        try:
            db.session.commit()
            flash('Template updated successfully!', 'success')
            return redirect(url_for('research_workflow.template_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating template: {str(e)}', 'error')
    
    # Get user's checklists and kill checklists for the step configuration
    user_checklists = [{'id': cl.id, 'name': cl.name} for cl in current_user.checklists.all()]
    user_kill_checklists = [{'id': kc.id, 'name': kc.name} for kc in current_user.kill_checklists.all()]
    
    # Define available step types and mental models (same as create)
    step_types = [
        {'value': 'checklist', 'label': 'Investment Checklist', 'icon': '📋'},
        {'value': 'kill_checklist_reference', 'label': 'Kill Checklist (Screening)', 'icon': '⚡'},
        {'value': 'model', 'label': 'Mental Model', 'icon': '🧠'},
        {'value': 'document_review', 'label': 'Document Analysis', 'icon': '📄'},
        {'value': 'valuation', 'label': 'Valuation Work', 'icon': '💰'},
        {'value': 'competitor_analysis', 'label': 'Competitor Analysis', 'icon': '🎯'},
        {'value': 'thesis_writing', 'label': 'Write Investment Thesis', 'icon': '✍️'},
        {'value': 'learning_overview', 'label': 'Learning Overview', 'icon': '📚'},
        {'value': 'concept_study', 'label': 'Concept Study', 'icon': '🎓'},
        {'value': 'industry_deep_dive', 'label': 'Industry Deep Dive', 'icon': '🏭'},
        {'value': 'business_model_analysis', 'label': 'Business Model Analysis', 'icon': '💼'},
        {'value': 'case_study', 'label': 'Case Study', 'icon': '📖'},
        {'value': 'custom', 'label': 'Custom Task', 'icon': '⚙️'}
    ]
    
    mental_models = [
        'SWOT Analysis',
        'Porter\'s Five Forces'
    ]
    
    return render_template('edit_template.html',
                          title=f"Edit Template: {template.name}",
                          template=template,
                          user_checklists=user_checklists,
                          user_kill_checklists=user_kill_checklists,
                          step_types=step_types,
                          mental_models=mental_models)

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

@research_workflow_bp.route('/templates/<int:template_id>/force-delete', methods=['POST'])
@login_required
def force_delete_template(template_id):
    """Force delete a research template even if it has been used"""
    template = ResearchTemplate.query.get_or_404(template_id)
    
    if template.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.template_list'))
    
    template_name = template.name
    project_count = ResearchProject.query.filter_by(template_id=template_id).count()
    
    try:
        db.session.delete(template)
        db.session.commit()
        flash(f'Template "{template_name}" deleted successfully. {project_count} existing projects remain unaffected.', 'success')
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
    project.last_worked_at = now_utc()
    
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
    
    project.last_worked_at = now_utc()
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Finding added'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500



@research_workflow_bp.route('/research_sessions/<int:session_id>/delete', methods=['POST'])
@login_required
def delete_research_session(session_id):
    """Delete a research session that is not in progress or completed"""
    session = ResearchSession.query.get_or_404(session_id)

    # Authorization check
    if session.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    # Allow deletion of in-progress sessions but with warning (handled in frontend)

    # For completed sessions, only allow deletion if they're incomplete/failed
    if session.status == 'completed':
        total_answers = ResearchAnswer.query.filter_by(research_session_id=session_id).all()
        total_item_count = len(total_answers)
        satisfied_count = len([ans for ans in total_answers if ans.satisfaction_status == 'satisfied'])

        # Don't allow deletion of successfully completed sessions
        if total_item_count > 0 and satisfied_count == total_item_count:
            flash('Cannot delete successfully completed research sessions', 'error')
            return redirect(url_for('research_workflow.my_projects'))

    try:
        # Delete related research answers first to handle foreign key constraints
        ResearchAnswer.query.filter_by(research_session_id=session_id).delete()

        # Commit the deletion of related records
        db.session.commit()

        # Delete the research session itself
        db.session.delete(session)
        db.session.commit()

        flash(f'Research session for "{session.company.name if session.company else "Unknown"}" has been deleted', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting research session: {str(e)}', 'error')

    return redirect(url_for('research_workflow.my_projects'))

@research_workflow_bp.route('/projects/<int:project_id>/delete', methods=['POST'])
@login_required
def delete_research_project(project_id):
    """Delete a research project"""
    project = ResearchProject.query.get_or_404(project_id)

    # Authorization check
    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    # Prevent deletion of completed projects with successful outcomes
    if project.status == 'completed' and project.decision in ['invest', 'pass']:
        flash('Cannot delete completed projects with investment decisions', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    try:
        project_name = project.research_subject_name or f"project"

        # If project is linked to an idea, we must handle its dependencies before deleting the idea itself.
        if project.idea:
            idea_to_delete = project.idea
            ResearchLog.query.filter_by(idea_id=idea_to_delete.id).delete(synchronize_session=False)
            JournalEntry.query.filter_by(idea_id=idea_to_delete.id).update({'idea_id': None}, synchronize_session=False)
            db.session.delete(idea_to_delete)

        # Clean up journal_entry references to this project
        JournalEntry.query.filter_by(project_id=project.id).update({'project_id': None}, synchronize_session=False)
        db.session.delete(project)
        db.session.commit()

        flash(f'Research project "{project_name}" has been deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting research project {project_id}: {str(e)}")
        # Provide a more specific error message if it's a foreign key violation
        if 'ForeignKeyViolation' in str(e):
             flash('Error deleting project: Could not remove related records. Please check for dependencies in other parts of the application.', 'error')
        else:
             flash(f'An unexpected error occurred while deleting the project.', 'error')

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
        project.completed_at = now_utc()
    
    project.last_worked_at = now_utc()
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Step skipped'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@research_workflow_bp.route('/projects/<int:project_id>/sessions/<int:session_id>/complete-checklist', methods=['POST'])
@login_required
def complete_checklist_step(project_id, session_id):
    """Complete a checklist step and save results"""
    project = ResearchProject.query.get_or_404(project_id)
    session = WorkSession.query.get_or_404(session_id)
    
    if project.user_id != current_user.id or session.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))
    
    # Get step details
    step = project.template.get_step(session.step_index)
    if not step or step['type'] != 'checklist':
        flash('Invalid checklist step', 'error')
        return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))
    
    # Process criteria evaluation results
    checklist_items = step['config'].get('checklist_items', [])
    analysis_notes = request.form.getlist('analysis_notes[]')
    item_notes = request.form.getlist('item_notes[]')
    step_notes = request.form.get('step_notes', '')
    
    # Process each criterion's evaluation
    criteria_evaluations = []
    met_count = 0
    critical_failed = 0
    total_evaluated = 0
    
    for i, item in enumerate(checklist_items):
        status = request.form.get(f'criteria_status_{i}')
        importance = request.form.get(f'criteria_importance_{i}', 'important')
        
        evaluation = {
            'index': i,
            'item_text': item['item'],
            'status': status,  # 'met', 'not_met', or 'not_applicable'
            'importance': importance,  # 'critical', 'important', 'nice_to_have'
            'notes': analysis_notes[i] if i < len(analysis_notes) else (item_notes[i] if i < len(item_notes) else '')
        }
        criteria_evaluations.append(evaluation)
        
        # Count results for summary
        if status == 'met':
            met_count += 1
            total_evaluated += 1
        elif status == 'not_met':
            if importance == 'critical':
                critical_failed += 1
            total_evaluated += 1
        # 'not_applicable' items don't count toward totals
    
    # Determine overall step result
    if total_evaluated == 0:
        step_result = 'incomplete'
        step_status_msg = 'No criteria were evaluated'
    elif critical_failed > 0:
        step_result = 'fail'
        step_status_msg = f'FAILED: {critical_failed} critical criteria not met'
    else:
        pass_rate = (met_count / total_evaluated) * 100 if total_evaluated > 0 else 0
        if pass_rate >= 80:  # 80% threshold for pass
            step_result = 'pass'
            step_status_msg = f'PASSED: {met_count}/{total_evaluated} criteria met ({pass_rate:.1f}%)'
        else:
            step_result = 'marginal'
            step_status_msg = f'MARGINAL: {met_count}/{total_evaluated} criteria met ({pass_rate:.1f}%) - Review required'
    
    # Build comprehensive results structure
    checklist_results = {
        'criteria_evaluations': criteria_evaluations,
        'total_items': len(checklist_items),
        'met_count': met_count,
        'total_evaluated': total_evaluated,
        'critical_failed': critical_failed,
        'step_result': step_result,
        'step_status_msg': step_status_msg,
        'pass_rate': (met_count / total_evaluated) * 100 if total_evaluated > 0 else 0
    }
    
    # Complete the session
    session.end_time = now_utc()
    start_time_aware = ensure_timezone_aware(session.start_time)
    session.duration_minutes = int((session.end_time - start_time_aware).total_seconds() / 60)
    session.notes = step_notes
    session.results = checklist_results
    session.status = 'completed'
    
    # Update project progress
    if not project.step_notes:
        project.step_notes = {}
    project.step_notes[str(session.step_index)] = step_notes
    
    if not project.step_results:
        project.step_results = {}
    project.step_results[str(session.step_index)] = checklist_results
    
    # Mark step as complete
    if not project.completed_steps:
        project.completed_steps = []
    
    if session.step_index not in project.completed_steps:
        project.completed_steps = project.completed_steps + [session.step_index]
    
    # Move to next step
    if session.step_index + 1 < len(project.template.workflow_steps):
        project.current_step_index = session.step_index + 1
    else:
        project.status = 'completed'
        project.completed_at = now_utc()
    
    project.last_worked_at = now_utc()
    
    try:
        db.session.commit()
        # Flash message based on step result
        if checklist_results['step_result'] == 'pass':
            flash(f'✅ {checklist_results["step_status_msg"]}', 'success')
        elif checklist_results['step_result'] == 'fail':
            flash(f'❌ {checklist_results["step_status_msg"]}', 'danger')
        elif checklist_results['step_result'] == 'marginal':
            flash(f'⚠️ {checklist_results["step_status_msg"]}', 'warning')
        else:
            flash(f'ℹ️ {checklist_results["step_status_msg"]}', 'info')
        
        if project.status == 'completed':
            return redirect(url_for('research_workflow.project_summary', project_id=project_id))
        else:
            return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))
            
    except Exception as e:
        db.session.rollback()
        flash('Error saving checklist results', 'error')
        return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))

@research_workflow_bp.route('/projects/<int:project_id>/sessions/<int:session_id>/complete-kill-checklist', methods=['POST'])
@login_required 
def complete_kill_checklist_step(project_id, session_id):
    """Complete a kill checklist step and save results"""
    project = ResearchProject.query.get_or_404(project_id)
    session = WorkSession.query.get_or_404(session_id)
    
    if project.user_id != current_user.id or session.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))
    
    # Get step details
    step = project.template.get_step(session.step_index)
    if not step or step['type'] != 'kill_checklist_reference':
        flash('Invalid kill checklist step', 'error')
        return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))
    
    kill_checklist_id = request.form.get('kill_checklist_id')
    overall_result = request.form.get('overall_result')  # 'proceed' or 'kill'
    step_notes = request.form.get('step_notes', '')
    
    # Process individual item results
    kill_checklist = KillChecklist.query.get(kill_checklist_id)
    item_results = []
    
    for item in kill_checklist.items:
        result = request.form.get(f'result_{item.id}')
        notes = request.form.get(f'notes_{item.id}', '')
        
        item_results.append({
            'item_id': item.id,
            'item_text': item.item_text,
            'result': result,  # 'pass' or 'fail'
            'notes': notes
        })
    
    # Calculate screening statistics
    pass_count = len([r for r in item_results if r['result'] == 'pass'])
    fail_count = len([r for r in item_results if r['result'] == 'fail'])
    
    kill_checklist_results = {
        'kill_checklist_id': kill_checklist_id,
        'kill_checklist_name': kill_checklist.name,
        'overall_result': overall_result,
        'item_results': item_results,
        'pass_count': pass_count,
        'fail_count': fail_count,
        'total_items': len(item_results),
        'screening_passed': overall_result == 'proceed'
    }
    
    # Complete the session
    session.end_time = now_utc()
    start_time_aware = ensure_timezone_aware(session.start_time)
    session.duration_minutes = int((session.end_time - start_time_aware).total_seconds() / 60)
    session.notes = step_notes
    session.results = kill_checklist_results
    session.status = 'completed'
    
    # Update project progress
    if not project.step_notes:
        project.step_notes = {}
    project.step_notes[str(session.step_index)] = step_notes
    
    if not project.step_results:
        project.step_results = {}
    project.step_results[str(session.step_index)] = kill_checklist_results
    
    # Mark step as complete (even if killed - it was completed)
    if not project.completed_steps:
        project.completed_steps = []
    
    if session.step_index not in project.completed_steps:
        project.completed_steps = project.completed_steps + [session.step_index]
    
    # Handle kill decision
    if overall_result == 'kill':
        project.status = 'killed'
        project.completed_at = now_utc()
        project.kill_reason = f"Failed screening: {step_notes}"
    else:
        # Move to next step
        if session.step_index + 1 < len(project.template.workflow_steps):
            project.current_step_index = session.step_index + 1
        else:
            project.status = 'completed'
            project.completed_at = now_utc()
    
    project.last_worked_at = now_utc()
    
    try:
        db.session.commit()
        
        if overall_result == 'kill':
            flash(f'Investment killed during screening. Failed {fail_count}/{len(item_results)} criteria.', 'warning')
            return redirect(url_for('research_workflow.project_summary', project_id=project_id))
        else:
            flash(f'Screening passed! {pass_count}/{len(item_results)} criteria met.', 'success')
            
            if project.status == 'completed':
                return redirect(url_for('research_workflow.project_summary', project_id=project_id))
            else:
                return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))
            
    except Exception as e:
        db.session.rollback()
        flash('Error saving screening results', 'error')
        return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))

@research_workflow_bp.route('/projects/<int:project_id>/sessions/<int:session_id>/save-checklist-progress', methods=['POST'])
@login_required
def save_checklist_progress(project_id, session_id):
    """Auto-save checklist progress"""
    # Simple auto-save endpoint for checklist progress
    return jsonify({'success': True, 'message': 'Progress saved'})

@research_workflow_bp.route('/projects/<int:project_id>/sessions/<int:session_id>/save-kill-checklist-progress', methods=['POST'])  
@login_required
def save_kill_checklist_progress(project_id, session_id):
    """Auto-save kill checklist progress"""
    # Simple auto-save endpoint for kill checklist progress
    return jsonify({'success': True, 'message': 'Progress saved'})

@research_workflow_bp.route('/templates/<int:template_id>/archive', methods=['POST'])
@login_required
def archive_template(template_id):
    """Archive a research template"""
    template = ResearchTemplate.query.get_or_404(template_id)
    
    if template.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.template_list'))
    
    template.is_active = False
    
    try:
        db.session.commit()
        flash(f'Template "{template.name}" archived successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error archiving template', 'error')
    
    return redirect(url_for('research_workflow.template_list'))

@research_workflow_bp.route('/templates/<int:template_id>/restore', methods=['POST'])
@login_required
def restore_template(template_id):
    """Restore an archived research template"""
    template = ResearchTemplate.query.get_or_404(template_id)
    
    if template.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.template_list'))
    
    template.is_active = True
    
    try:
        db.session.commit()
        flash(f'Template "{template.name}" restored successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error restoring template', 'error')
    
    return redirect(url_for('research_workflow.template_list'))

@research_workflow_bp.route('/projects/<int:project_id>/sessions/<int:session_id>/checklist_item_analyze', methods=['POST'])
@login_required
def analyze_checklist_item(project_id, session_id):
    """AI analysis for Research Template checklist items"""
    # Get and validate project and session
    project = ResearchProject.query.get_or_404(project_id)
    session = WorkSession.query.get_or_404(session_id)
    
    if project.user_id != current_user.id or session.user_id != current_user.id:
        return jsonify({'status': 'error', 'message': 'Access denied'}), 403
    
    if session.research_project_id != project_id:
        return jsonify({'status': 'error', 'message': 'Invalid session for project'}), 400
    
    # Check Gemini API configuration
    gemini_api_key = current_app.config.get('GEMINI_API_KEY')
    if not gemini_api_key:
        return jsonify({
            'status': 'error_config', 
            'message': 'Gemini API key not configured. Please check server configuration.'
        }), 500
    
    # LLM service will handle API configuration automatically
    
    # Parse request data
    if not request.is_json:
        return jsonify({'status': 'error', 'message': 'Request must be JSON'}), 400
    
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'No JSON data received'}), 400
    
    # Extract parameters
    item_index = data.get('item_index')  # Index of the checklist item
    llm_prompt = data.get('llm_prompt', '')
    selected_document_ids = data.get('selected_document_ids', [])
    
    if item_index is None:
        return jsonify({'status': 'error', 'message': 'item_index is required'}), 400
    
    if not llm_prompt:
        return jsonify({
            'status': 'error_no_prompt', 
            'message': 'No LLM prompt provided for analysis'
        }), 400
    
    # Get the current step and validate the item index
    step = project.template.get_step(session.step_index)
    if not step or step['type'] != 'checklist':
        return jsonify({'status': 'error', 'message': 'Invalid step or not a checklist step'}), 400
    
    checklist_items = step['config'].get('checklist_items', [])
    if item_index >= len(checklist_items):
        return jsonify({'status': 'error', 'message': 'Invalid item index'}), 400
    
    # Handle document processing for company projects only
    documents = []
    if selected_document_ids and project.company_id:
        try:
            doc_ids = [int(doc_id) for doc_id in selected_document_ids]
            documents = CompanyDocument.query.filter(
                CompanyDocument.id.in_(doc_ids),
                CompanyDocument.company_id == project.company_id
            ).all()
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Invalid document ID format'}), 400
    
    # Process documents and extract text (simplified approach)
    document_context = ""
    processed_docs_info = []
    
    if documents:
        for doc in documents:
            try:
                # Simple text extraction - in a real implementation you'd want proper document processing
                with open(doc.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    doc_text = f.read()[:2000]  # Limit to first 2000 chars per doc
                    document_context += f"\n\n=== {doc.title or doc.filename} ===\n{doc_text}"
                    processed_docs_info.append({
                        'id': doc.id,
                        'title': doc.title,
                        'filename': doc.filename
                    })
            except Exception as e:
                print(f"Error processing document {doc.id}: {e}")
                continue
    
    # Prepare the analysis prompt
    item_text = checklist_items[item_index]['item']
    analysis_context = f"""Research Context:
- Subject: {project.subject_display_name}
- Template: {project.template.name}
- Current Step: {step['name']}
- Checklist Item: {item_text}

User's Analysis Request:
{llm_prompt}
"""
    
    if document_context:
        analysis_context += f"\n\nAvailable Documents:{document_context}"
    else:
        analysis_context += "\n\nNo documents were provided for analysis."
    
    # Generate AI analysis using unified LLM service
    try:
        ai_suggestion = generate_ai_content(analysis_context)
        
        return jsonify({
            'status': 'success_analysis_complete',
            'message': 'Analysis completed successfully',
            'ai_suggestion': ai_suggestion,
            'received_prompt': llm_prompt,
            'item_text': item_text,
            'selected_documents_info': processed_docs_info,
            'extracted_text_sample': document_context[:500] + '...' if len(document_context) > 500 else document_context
        })
        
    except Exception as e:
        error_msg = str(e)
        print(f"Gemini API error: {error_msg}")
        
        return jsonify({
            'status': 'error_ai_failed',
            'message': f'AI analysis failed: {error_msg}',
            'received_prompt': llm_prompt,
            'selected_documents_info': processed_docs_info
        }), 500

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

@research_workflow_bp.route('/return-from-checklist/<int:project_id>/<int:step_index>')
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


# Adaptive Research Template API Routes

@research_workflow_bp.route('/api/template/<int:template_id>/adaptations')
@login_required
def get_template_adaptations(template_id):
    """Get adaptive suggestions for a research template based on company context"""
    template = ResearchTemplate.query.get_or_404(template_id)

    # Security check
    if template.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    # Get company from request parameters
    company_id = request.args.get('company_id', type=int)
    if not company_id:
        return jsonify({'error': 'Company ID required'}), 400

    company = Company.query.get_or_404(company_id)
    if company.user_id != current_user.id:
        return jsonify({'error': 'Access denied to company'}), 403

    try:
        logger.info(f"Getting adaptations for template {template_id}, company {company_id}")

        # Get comprehensive adaptations
        adaptations = suggest_template_adaptations(template, company, current_user.id)

        logger.info(f"Successfully generated adaptations: {adaptations}")

        return jsonify({
            'success': True,
            'adaptations': adaptations,
            'template_id': template_id,
            'company_id': company_id
        })

    except Exception as e:
        logger.error(f"Error getting template adaptations: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
        }), 500


@research_workflow_bp.route('/api/template/<int:template_id>/apply-adaptations', methods=['POST'])
@login_required
def apply_adaptations(template_id):
    """Apply selected adaptations to a research template"""
    template = ResearchTemplate.query.get_or_404(template_id)

    # Security check
    if template.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No adaptation data provided'}), 400

        # Apply the adaptations
        success = apply_template_adaptations(template, data)

        if success:
            return jsonify({
                'success': True,
                'message': 'Template adaptations applied successfully',
                'template_id': template_id
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to apply adaptations'
            }), 500

    except Exception as e:
        logger.error(f"Error applying template adaptations: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@research_workflow_bp.route('/api/template/<int:template_id>/time-estimates')
@login_required
def get_personalized_time_estimates(template_id):
    """Get personalized time estimates for template steps based on user history"""
    template = ResearchTemplate.query.get_or_404(template_id)

    # Security check
    if template.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    try:
        estimates = adaptive_template_service.get_personalized_time_estimates(
            template, current_user.id
        )

        return jsonify({
            'success': True,
            'estimates': estimates,
            'template_id': template_id
        })

    except Exception as e:
        logger.error(f"Error getting time estimates: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@research_workflow_bp.route('/api/company/<int:company_id>/sector-questions')
@login_required
def get_sector_questions(company_id):
    """Get sector-specific questions available for a company"""
    company = Company.query.get_or_404(company_id)

    # Security check
    if company.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    try:
        if not company.sector:
            return jsonify({
                'success': True,
                'questions': [],
                'message': 'No sector specified for this company'
            })

        questions = adaptive_template_service.get_sector_questions(
            company.sector, current_user.id
        )

        return jsonify({
            'success': True,
            'questions': questions,
            'sector': company.sector,
            'company_id': company_id
        })

    except Exception as e:
        logger.error(f"Error getting sector questions: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@research_workflow_bp.route('/api/project/<int:project_id>/adaptive-suggestions')
@login_required
def get_project_adaptive_suggestions(project_id):
    """Get adaptive suggestions when starting a new research project"""
    project = ResearchProject.query.get_or_404(project_id)

    # Security check
    if project.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    try:
        template = project.template
        company = project.company

        logger.info(f"Getting project suggestions for project {project_id}, template: {template.id if template else 'None'}, company: {company.id if company else 'None'}")

        if not company:
            logger.warning(f"Project {project_id} has no company associated")
            return jsonify({
                'success': True,
                'suggestions': [],
                'message': 'No company associated with this project'
            })

        if not company.sector:
            logger.warning(f"Company {company.id} has no sector specified")
            return jsonify({
                'success': True,
                'suggestions': [],
                'message': f'No sector specified for {company.name}'
            })

        # Get comprehensive suggestions
        adaptations = suggest_template_adaptations(template, company, current_user.id)

        # Calculate potential time savings/additions
        step_suggestions = adaptations.get('step_injections', {}).get('suggestions', [])
        time_estimates = adaptations.get('time_estimates', {}).get('estimates', [])

        # Create actionable suggestions summary
        suggestions_summary = {
            'sector_questions_available': len(step_suggestions),
            'time_estimates_available': len([e for e in time_estimates if e.get('confidence', 0) > 0.5]),
            'recommended_injections': [
                {
                    'step_name': s['step_name'],
                    'questions_count': len(s['questions']),
                    'confidence': s['confidence']
                }
                for s in step_suggestions
                if s['confidence'] > 0.7
            ],
            'time_insights': adaptations.get('time_estimates', {}).get('insights', [])
        }

        return jsonify({
            'success': True,
            'suggestions': suggestions_summary,
            'full_adaptations': adaptations,
            'project_id': project_id
        })

    except Exception as e:
        logger.error(f"Error getting project adaptive suggestions: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
        }), 500