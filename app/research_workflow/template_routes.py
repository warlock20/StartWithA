# StartWithA
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

"""
Template Management Routes Module

This module handles all routes related to research template management including:
- Listing templates
- Creating new templates
- Viewing template details
- Editing templates
- Deleting and force deleting templates
- Archiving and restoring templates
- Creating default templates for users
"""

from flask import render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from app import db
from app.models import ResearchTemplate, ResearchProject, Company, Checklist, ChecklistItem
from app.research_workflow import research_workflow_bp
from app.utils.decorators import require_feature
from app.utils.time_utils import now_utc
import json

# Available step types for research templates
STEP_TYPES = [
    {'value': 'checklist', 'label': 'Investment Checklist', 'icon': '📋'},
    {'value': 'model', 'label': 'Mental Model', 'icon': '🧠'},
    {'value': 'free_research', 'label': 'Free Research', 'icon': '🔍'},
    {'value': 'competitor_analysis', 'label': 'Competitor Analysis', 'icon': '🎯'},
    {'value': 'thesis_writing', 'label': 'Write Investment Thesis', 'icon': '✍️'},
    {'value': 'custom', 'label': 'Custom Task', 'icon': '⚙️'}
]

MENTAL_MODELS = [
    'SWOT Analysis',
]


def ensure_default_template(user):
    """Create a default research template if the user has none.

    Also creates a default investment checklist so the checklist step
    in the template has something to reference.

    Returns:
        tuple: (template, is_new) — is_new=True if just created.
    """
    template = ResearchTemplate.query.filter_by(user_id=user.id, is_active=True).first()
    if template:
        return template, False

    # ── Create default investment checklist ─────────────────────────
    checklist = Checklist.query.filter_by(user_id=user.id).first()
    if not checklist:
        checklist = Checklist(user_id=user.id, name='Basic Investment Analysis',
                              description='A comprehensive starting point for evaluating any investment opportunity')
        db.session.add(checklist)
        db.session.flush()

        default_items = [
            ('Business Model & Strategy', [
                'What products/services does the company sell?',
                'Who are the target customers?',
                'What is the competitive advantage?',
                'How does the company generate revenue?',
            ]),
            ('Financial Performance Review', [
                'Revenue growth trend over the past 5 years',
                'Profitability metrics and margin analysis',
                'Cash flow vs. net income comparison',
                'Debt levels and capital structure',
            ]),
            ('Management Quality Assessment', [
                'Executive team background and track record',
                'Capital allocation track record',
                'Insider trading activity',
            ]),
            ('Competitive Position Analysis', [
                'Identify main competitors',
                'Market share analysis',
                'Barriers to entry evaluation',
            ]),
            ('Valuation & Investment Decision', [
                'P/E ratio vs. historical average',
                'Peer valuation comparison',
                'Margin of safety calculation',
            ]),
        ]

        for order, (section_text, subitems) in enumerate(default_items):
            parent = ChecklistItem(checklist_id=checklist.id, text=section_text, order=order)
            db.session.add(parent)
            db.session.flush()
            for sub_order, sub_text in enumerate(subitems):
                db.session.add(ChecklistItem(
                    checklist_id=checklist.id, text=sub_text,
                    parent_id=parent.id, order=sub_order))

    # ── Create default research template ────────────────────────────
    workflow_steps = [
        {'order': 1, 'name': 'Initial Financial Screening', 'type': 'checklist',
         'config': {'checklist_id': str(checklist.id) if checklist else ''},
         'required': True, 'estimated_minutes': 30},
        {'order': 2, 'name': 'Business Model Analysis', 'type': 'custom',
         'config': {}, 'required': True, 'estimated_minutes': 60},
        {'order': 3, 'name': 'Management Assessment', 'type': 'custom',
         'config': {}, 'required': False, 'estimated_minutes': 45},
        {'order': 4, 'name': 'Competitive Position Review', 'type': 'competitor_analysis',
         'config': {}, 'required': True, 'estimated_minutes': 90},
        {'order': 5, 'name': 'Valuation Analysis', 'type': 'custom',
         'config': {}, 'required': True, 'estimated_minutes': 120},
        {'order': 6, 'name': 'Risk Assessment', 'type': 'custom',
         'config': {}, 'required': True, 'estimated_minutes': 60},
        {'order': 7, 'name': 'Investment Thesis', 'type': 'thesis_writing',
         'config': {}, 'required': True, 'estimated_minutes': 45},
    ]

    template = ResearchTemplate(
        author=user,
        name='Fundamental Analysis Workflow',
        description='A step-by-step workflow for fundamental stock analysis covering financials, business quality, and valuation.',
        investment_style='value',
        workflow_steps=workflow_steps,
        is_active=True,
    )
    db.session.add(template)
    db.session.commit()
    return template, True


@research_workflow_bp.route('/templates')
@login_required
@require_feature('research_templates')
def template_list():
    """Display all research templates for the current user with sorting and pagination"""
    # Get sort parameter (default: recent)
    sort = request.args.get('sort', 'recent')
    page = request.args.get('page', 1, type=int)
    per_page = 8

    # Base query
    query = current_user.research_templates

    # Apply sorting
    if sort == 'name':
        query = query.order_by(ResearchTemplate.name.asc())
    elif sort == 'steps':
        # Sort by number of steps (using JSON array length)
        query = query.order_by(db.func.json_array_length(ResearchTemplate.workflow_steps).desc())
    elif sort == 'uses':
        query = query.order_by(ResearchTemplate.times_used.desc())
    elif sort == 'success':
        # Calculate success rate in SQL: successful / (successful + failed)
        # Use CASE to handle division by zero
        total_investments = ResearchTemplate.successful_investments + ResearchTemplate.failed_investments
        success_rate_expr = db.case(
            (total_investments > 0,
             (ResearchTemplate.successful_investments * 100.0 / total_investments)),
            else_=0
        )
        query = query.order_by(success_rate_expr.desc())
    elif sort == 'oldest':
        query = query.order_by(ResearchTemplate.created_at.asc())
    else:  # recent (default)
        query = query.order_by(ResearchTemplate.updated_at.desc())

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    templates = pagination.items

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
                          pagination=pagination,
                          total_projects=total_projects,
                          active_projects=active_projects,
                          total_research_hours=round(total_research_hours, 1),
                          context=context)



@research_workflow_bp.route('/templates/create', methods=['GET', 'POST'])
@login_required
@require_feature('research_templates')
def create_template():
    """Create a new research template"""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        investment_style = request.form.get('investment_style')
        custom_investment_style = request.form.get('custom_investment_style')

        # Use custom investment style if selected
        if investment_style == 'custom' and custom_investment_style:
            investment_style = custom_investment_style.strip()

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
        
        # Create the template (company-only)
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
    
    # Get user's checklists and kill checklists for the step configuration
    user_checklists = [{'id': cl.id, 'name': cl.name} for cl in current_user.checklists.all()]
    user_kill_checklists = [{'id': kc.id, 'name': kc.name} for kc in current_user.kill_checklists.all()]
    
    return render_template('create_template.html',
                          title="Create Research Template",
                          user_checklists=user_checklists,
                          user_kill_checklists=user_kill_checklists,
                          step_types=STEP_TYPES,
                          mental_models=MENTAL_MODELS)



@research_workflow_bp.route('/templates/<int:template_id>/view')
@login_required
@require_feature('research_templates')
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



@research_workflow_bp.route('/templates/<int:template_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_template(template_id):
    """Edit an existing research template"""
    template = ResearchTemplate.query.get_or_404(template_id)
    
    if template.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

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
            flash('Workflow updated successfully!', 'success')
            return redirect(url_for('research_workflow.my_projects'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating template: {str(e)}', 'error')

    # Get user's checklists and kill checklists for the step configuration
    user_checklists = [{'id': cl.id, 'name': cl.name} for cl in current_user.checklists.all()]
    user_kill_checklists = [{'id': kc.id, 'name': kc.name} for kc in current_user.kill_checklists.all()]

    return render_template('create_template.html',
                          title=f"Edit Workflow: {template.name}",
                          template=template,
                          user_checklists=user_checklists,
                          user_kill_checklists=user_kill_checklists,
                          step_types=STEP_TYPES,
                          mental_models=MENTAL_MODELS)



@research_workflow_bp.route('/templates/<int:template_id>/delete', methods=['POST'])
@login_required
@require_feature('research_templates')
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
@require_feature('research_templates')
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


@research_workflow_bp.route('/templates/<int:template_id>/archive', methods=['POST'])
@login_required
@require_feature('research_templates')
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
@require_feature('research_templates')
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

