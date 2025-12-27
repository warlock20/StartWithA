"""
Utility Routes Module

This module handles utility and navigation routes including:
- Intelligent routing for company-based research
- Quick start guide for new users
- Research initiation page
"""

from flask import render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from app.models import ResearchTemplate, ResearchProject, Company
from app.research_workflow import research_workflow_bp


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


@research_workflow_bp.route('/start-new')
@login_required
def start_new_research():
    """Subject type selection page for starting new research"""
    return render_template('start_new_research.html',
                          title="Start New Research")


@research_workflow_bp.route('/quick-start', methods=['GET'])
@login_required
def quick_start_guide():
    """Show a quick start guide for new users"""
    from app.research_workflow.template_routes import create_default_template_for_user

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
