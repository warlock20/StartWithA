"""
Project Management Routes Module

This module handles all routes related to project listing, filtering, and management including:
- Project dashboard and listings
- Active, completed, paused, and "too hard basket" project views
- Project state management (pause, resume, delete)
- Project filtering and pagination

Extracted from routes.py lines: 314-392, 394-445, 447-497, 499-555, 557-648, 650-670,
672-692, 756-797
"""

from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import current_user, login_required
from app import db
from app.models import (ResearchTemplate, ResearchProject, Company,
                       ResearchLog, JournalEntry, IdeaPipeline)
from app.research_workflow import research_workflow_bp
from app.utils.time_utils import now_utc, ensure_timezone_aware


@research_workflow_bp.route('/my-projects')
@login_required
def my_projects():
    """Dashboard view for all research projects"""
    # Get counts for different project statuses
    active_count = current_user.research_projects.filter_by(status='active').count()
    paused_count = current_user.research_projects.filter_by(status='paused').count()
    completed_count = current_user.research_projects.filter_by(status='completed').count()

    # Get Too Hard Basket count (completed projects with 'pass' decision)
    too_hard_count = current_user.research_projects.filter_by(
        status='completed',
        decision='pass'
    ).count()

    # Calculate total time invested
    total_time_invested = sum(p.total_hours_spent for p in current_user.research_projects.all())

    # Success metrics
    invest_decisions = current_user.research_projects.filter_by(decision='invest').count()
    pass_decisions = current_user.research_projects.filter_by(decision='pass').count()
    watchlist_decisions = current_user.research_projects.filter_by(decision='watchlist').count()

    # Calculate Too Hard Basket Rate (selectivity metric)
    # Count projects with invest or pass decisions
    company_invest_count = current_user.research_projects.filter_by(
        decision='invest'
    ).count()

    company_pass_count = current_user.research_projects.filter_by(
        decision='pass'
    ).count()

    total_decided_companies = company_invest_count + company_pass_count

    if total_decided_companies > 0:
        too_hard_rate = (company_pass_count / total_decided_companies) * 100
    else:
        too_hard_rate = 0

    # Get recent activity (last 5 projects worked on)
    recent_activity = current_user.research_projects.order_by(
        ResearchProject.last_worked_at.desc()
    ).limit(5).all()

    # Get preview data for each section (top 3)
    active_preview = current_user.research_projects.filter_by(status='active')\
        .order_by(ResearchProject.last_worked_at.desc()).limit(3).all()

    completed_preview = current_user.research_projects.filter_by(status='completed')\
        .order_by(ResearchProject.completed_at.desc()).limit(3).all()

    too_hard_preview = current_user.research_projects.filter_by(
        status='completed',
        decision='pass'
    ).order_by(ResearchProject.completed_at.desc()).limit(3).all()

    dashboard_data = {
        'active_count': active_count,
        'paused_count': paused_count,
        'completed_count': completed_count,
        'too_hard_count': too_hard_count,
        'total_time_invested': round(total_time_invested, 1),
        'invest_decisions': invest_decisions,
        'pass_decisions': pass_decisions,
        'watchlist_decisions': watchlist_decisions,
        'too_hard_rate': round(too_hard_rate, 1),
        'total_decided_companies': total_decided_companies,
        'company_invest_count': company_invest_count,
        'company_pass_count': company_pass_count,
        'recent_activity': recent_activity,
        'active_preview': active_preview,
        'completed_preview': completed_preview,
        'too_hard_preview': too_hard_preview
    }

    return render_template('projects_dashboard.html',
                          title="Investment Research",
                          dashboard_data=dashboard_data)


@research_workflow_bp.route('/my-projects/active')
@login_required
def active_projects():
    """Detailed view of active research projects with pagination and filters"""
    # Get query parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search_query = request.args.get('search', '', type=str).strip()
    type_filter = request.args.get('type', '', type=str).strip()

    # Base query for active projects
    query = current_user.research_projects.filter_by(status='active')

    # Apply search filter
    if search_query:
        # Search in company name or project name
        query = query.filter(
            db.or_(
                ResearchProject.project_name.ilike(f'%{search_query}%'),
                ResearchProject.company.has(Company.name.ilike(f'%{search_query}%'))
            )
        )

    # Type filter removed - all projects are company projects now

    # Order by last worked date
    query = query.order_by(ResearchProject.last_worked_at.desc())

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    active_projects = pagination.items

    # Flag overdue projects
    overdue_projects = [p for p in active_projects if p.is_overdue]

    # Get paused projects (no pagination for this smaller section)
    paused_projects = current_user.research_projects.filter_by(status='paused')\
        .order_by(ResearchProject.created_at.desc()).all()

    # All projects are company type now
    types = ['company']

    return render_template('projects_active.html',
                          title="Active Research Projects",
                          active_projects=active_projects,
                          pagination=pagination,
                          paused_projects=paused_projects,
                          overdue_projects=overdue_projects,
                          project_types=types,
                          current_search=search_query,
                          current_type=type_filter,
                          current_per_page=per_page)


@research_workflow_bp.route('/my-projects/completed')
@login_required
def completed_projects():
    """Detailed view of completed research projects"""
    # Get pagination and filter parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search_query = request.args.get('search', '', type=str).strip()
    decision_filter = request.args.get('decision', '', type=str).strip()

    # Start with base query - only show projects with a final decision
    query = current_user.research_projects.filter(ResearchProject.status == 'completed')

    # Apply search filter
    if search_query:
        query = query.join(Company, ResearchProject.company_id == Company.id, isouter=True)\
            .filter(
                db.or_(
                    Company.name.ilike(f'%{search_query}%'),
                    Company.ticker_symbol.ilike(f'%{search_query}%')
                )
            )

    # Apply decision filter
    if decision_filter:
        query = query.filter(ResearchProject.decision == decision_filter)

    # Order by completed time (most recent first)
    query = query.order_by(ResearchProject.completed_at.desc())

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    completed_projects = pagination.items

    # Get unique decisions for filter dropdown
    all_decisions = db.session.query(ResearchProject.decision)\
        .filter(
            ResearchProject.user_id == current_user.id,
            ResearchProject.status == 'completed',
            ResearchProject.decision.isnot(None)
        ).distinct().all()
    decisions = [d[0] for d in all_decisions if d[0]]

    return render_template('projects_completed.html',
                          title="Completed Research Projects",
                          completed_projects=completed_projects,
                          pagination=pagination,
                          current_search=search_query,
                          current_decision=decision_filter,
                          current_per_page=per_page,
                          decisions=decisions)


@research_workflow_bp.route('/my-projects/too-hard-basket')
@login_required
def too_hard_basket_legacy():
    """Legacy route - redirect to unified Too Hard Basket"""
    # Redirect to new unified route, preserving query parameters
    return redirect(url_for('research_workflow.too_hard_basket', **request.args))


@research_workflow_bp.route('/my-projects/paused')
@login_required
def paused_projects():
    """Detailed view of paused research projects"""
    # Get pagination and filter parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search_query = request.args.get('search', '', type=str).strip()
    template_filter = request.args.get('template', '', type=str).strip()
    sort_order = request.args.get('sort', 'recent', type=str)  # recent or oldest

    # Start with base query
    query = current_user.research_projects.filter_by(status='paused')

    # Apply search filter
    if search_query:
        query = query.join(Company, ResearchProject.company_id == Company.id, isouter=True)\
            .filter(
                db.or_(
                    Company.name.ilike(f'%{search_query}%'),
                    Company.ticker_symbol.ilike(f'%{search_query}%')
                )
            )

    # Apply template filter
    if template_filter:
        query = query.filter(ResearchProject.template_id == int(template_filter))

    # Order by last worked time
    if sort_order == 'oldest':
        query = query.order_by(ResearchProject.last_worked_at.asc())
    else:  # recent
        query = query.order_by(ResearchProject.last_worked_at.desc())

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    paused_projects = pagination.items

    # Get unique templates for filter dropdown
    all_templates = db.session.query(ResearchTemplate.id, ResearchTemplate.name)\
        .join(ResearchProject, ResearchProject.template_id == ResearchTemplate.id)\
        .filter(
            ResearchProject.user_id == current_user.id,
            ResearchProject.status == 'paused'
        ).distinct().all()
    templates = [{'id': t[0], 'name': t[1]} for t in all_templates]

    # Calculate paused duration for each project
    current_time = now_utc()
    projects_with_duration = []
    for project in paused_projects:
        project_data = {
            'project': project,
            'days_paused': 0,
            'duration_text': 'Unknown',
            'duration_class': 'text-muted'
        }

        if project.last_worked_at:
            last_worked_aware = ensure_timezone_aware(project.last_worked_at)
            days_paused = (current_time - last_worked_aware).days
            project_data['days_paused'] = days_paused

            if days_paused < 1:
                project_data['duration_text'] = 'Today'
                project_data['duration_class'] = 'text-muted'
            elif days_paused == 1:
                project_data['duration_text'] = '1 day'
                project_data['duration_class'] = 'text-muted'
            elif days_paused < 7:
                project_data['duration_text'] = f'{days_paused} days'
                project_data['duration_class'] = 'text-muted'
            elif days_paused < 30:
                weeks = days_paused // 7
                project_data['duration_text'] = f'{weeks} week{"s" if weeks > 1 else ""}'
                project_data['duration_class'] = 'text-warning'
            else:
                months = days_paused // 30
                project_data['duration_text'] = f'{months} month{"s" if months > 1 else ""}'
                project_data['duration_class'] = 'text-danger'

        projects_with_duration.append(project_data)

    return render_template('projects_paused.html',
                          title="Paused Research Projects",
                          projects_with_duration=projects_with_duration,
                          pagination=pagination,
                          current_search=search_query,
                          current_template=template_filter,
                          current_sort=sort_order,
                          current_per_page=per_page,
                          templates=templates)


@research_workflow_bp.route('/projects/<int:project_id>/pause', methods=['POST'])
@login_required
def pause_project(project_id):
    """Pause functionality removed - redirect to mark as too hard"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    flash('Pause functionality has been replaced with "Mark as Too Hard". If you want to stop research on this project, please mark it as too hard instead.', 'info')
    return redirect(url_for('research_workflow.mark_too_hard', project_id=project_id))


@research_workflow_bp.route('/projects/<int:project_id>/resume', methods=['POST'])
@login_required
def resume_project(project_id):
    """Resume functionality - convert paused projects to active"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('research_workflow.my_projects'))

    # If somehow a paused project still exists, convert it to active
    if project.status == 'paused':
        project.status = 'active'
        project.last_worked_at = now_utc()

        try:
            db.session.commit()
            flash(f'Project "{project.project_name}" resumed', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error resuming project: {str(e)}', 'error')
            return redirect(url_for('research_workflow.my_projects'))

    return redirect(url_for('research_workflow.project_dashboard', project_id=project_id))


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
