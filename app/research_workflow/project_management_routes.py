"""
Project Management Routes Module

This module handles all routes related to project listing, filtering, and management including:
- Project dashboard and listings
- Active, completed, paused, and "too hard basket" project views
- Project state management (pause, resume, delete)
- Project filtering and pagination
"""

from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import current_user, login_required
from app import db
from app.models import (ResearchTemplate, ResearchProject, Company,
                       ResearchLog, JournalEntry, IdeaPipeline)
from app.research_workflow import research_workflow_bp
from app.utils.time_utils import now_utc, ensure_timezone_aware
from app.services.too_hard_service import TooHardBasketService
from app.services.sector_service import SectorService

@research_workflow_bp.route('/my-projects')
@login_required
def my_projects():
    """Dashboard view for all research projects"""
    # Get counts for different project statuses
    active_count = current_user.research_projects.filter_by(status='active').count()
    paused_count = current_user.research_projects.filter_by(status='paused').count()
    completed_count = current_user.research_projects.filter_by(status='completed').count()

    # Get Too Hard Basket count (includes: killed ideas and all passed projects)
    all_too_hard_items = TooHardBasketService.get_all_too_hard_companies(current_user.id, {})
    too_hard_count = len(all_too_hard_items)

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

    # Get top 3 too hard items for preview (includes all sources from service)
    too_hard_preview = all_too_hard_items[:3] if all_too_hard_items else []

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
def too_hard_basket():
    """View all rejected companies (unified Too Hard Basket)"""
    from app.services.too_hard_service import TooHardBasketService

    # Get filter parameters
    stage_filter = request.args.get('stage')
    search_query = request.args.get('search', '').strip()
    sector_filter = request.args.get('sector')
    coc_filter = request.args.get('coc')
    sort_by = request.args.get('sort', 'date_desc')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    # Build filters dict
    filters = {}
    if stage_filter:
        filters['rejection_stage'] = stage_filter
    if search_query:
        filters['search'] = search_query
    if sector_filter:
        filters['sector'] = sector_filter
    if coc_filter:
        filters['within_coc'] = coc_filter

    # Get all too hard companies
    all_items = TooHardBasketService.get_all_too_hard_companies(
        user_id=current_user.id,
        filters=filters
    )

    # Sort items
    if sort_by == 'date_desc':
        all_items.sort(key=lambda x: x.rejection_date or datetime.min, reverse=True)
    elif sort_by == 'date_asc':
        all_items.sort(key=lambda x: x.rejection_date or datetime.min)
    elif sort_by == 'time_desc':
        all_items.sort(key=lambda x: x.time_invested_hours, reverse=True)
    elif sort_by == 'name_asc':
        all_items.sort(key=lambda x: x.company_name.lower())

    # Calculate stage counts (without filters for accurate counts)
    all_unfiltered = TooHardBasketService.get_all_too_hard_companies(current_user.id)
    total_count = len(all_unfiltered)
    kill_count = sum(1 for item in all_unfiltered if item.rejection_stage == 'kill_checklist')
    mid_research_count = sum(1 for item in all_unfiltered if item.rejection_stage == 'mid_research')
    full_analysis_count = sum(1 for item in all_unfiltered if item.rejection_stage == 'full_analysis')

    # Paginate results
    total_items = len(all_items)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    items = all_items[start_idx:end_idx]

    # Create pagination object
    class SimplePagination:
        def __init__(self, page, per_page, total):
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1 if self.has_prev else None
            self.next_num = page + 1 if self.has_next else None

    pagination = SimplePagination(page, per_page, total_items)
    sectors_list = SectorService.get_user_sectors_list(current_user.id)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template('partials/_too_hard_list.html', 
                               too_hard_items=items, 
                               pagination=pagination,
                               current_stage=stage_filter)  
                               
    return render_template('too_hard_basket.html',
                          too_hard_items=items,
                          sectors_list=sectors_list,
                          pagination=pagination,
                          search_query=search_query,
                          current_stage=stage_filter,
                          current_sector=sector_filter,
                          current_coc=coc_filter,
                          sort_by=sort_by,
                          current_per_page=per_page,
                          total_count=total_count,
                          kill_count=kill_count,
                          mid_research_count=mid_research_count,
                          full_analysis_count=full_analysis_count)


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
        project_name = project.subject_display_name or "project"

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
