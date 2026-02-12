"""
Project Management Routes Module

This module handles the unified Company Research page and project management including:
- Unified Company Research dashboard (Active Research, Watchlist, Too Hard)
- Project state management (pause, resume, delete)
- Legacy route redirects for removed sub-pages
"""

import json
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
    """Unified Company Research page — Active Research, Watchlist, Too Hard"""

    # --- Active Research (active + paused) ---
    active_projects = current_user.research_projects.filter(
        ResearchProject.status.in_(['active', 'paused'])
    ).order_by(ResearchProject.last_worked_at.desc()).all()

    active_data = []
    for p in active_projects:
        active_data.append({
            'id': p.id,
            'company_name': p.subject_display_name,
            'ticker': p.company.ticker_symbol if p.company else '',
            'template_name': p.template.name if p.template else 'Custom',
            'progress': p.progress_percentage,
            'status': p.status,
            'last_worked': p.last_worked_at.isoformat() if p.last_worked_at else None,
            'hours_spent': round(p.total_hours_spent or 0, 1),
            'is_overdue': p.is_overdue,
            'company_id': p.company_id,
            'dashboard_url': url_for('research_workflow.project_dashboard', project_id=p.id),
        })

    # --- Watchlist (favorites not in portfolio + watchlist decisions) ---
    favorite_ids = {c.id for c in current_user.favorites.all()}
    all_user_companies = Company.query.filter_by(user_id=current_user.id).all()
    portfolio_ids = {c.id for c in all_user_companies if c.is_in_portfolio}

    manual_watchlist = [c for c in all_user_companies
                        if c.id in favorite_ids and c.id not in portfolio_ids]

    watchlist_projects = current_user.research_projects.filter_by(
        status='completed', decision='watchlist'
    ).all()
    watchlist_company_ids = {p.company_id for p in watchlist_projects}

    watchlist_data = []
    seen_ids = set()

    for c in manual_watchlist:
        seen_ids.add(c.id)
        source = 'Research Decision' if c.id in watchlist_company_ids else 'Manual Add'
        watchlist_data.append({
            'company_id': c.id,
            'company_name': c.name,
            'ticker': c.ticker_symbol or '',
            'sector': c.sector.name if c.sector else 'N/A',
            'source': source,
            'company_url': url_for('companies.company_dashboard', company_id=c.id),
        })

    for p in watchlist_projects:
        if p.company_id and p.company_id not in seen_ids:
            c = p.company
            if c:
                seen_ids.add(c.id)
                watchlist_data.append({
                    'company_id': c.id,
                    'company_name': c.name,
                    'ticker': c.ticker_symbol or '',
                    'sector': c.sector.name if c.sector else 'N/A',
                    'source': 'Research Decision',
                    'company_url': url_for('companies.company_dashboard', company_id=c.id),
                })

    # --- Too Hard / Passed ---
    all_too_hard_items = TooHardBasketService.get_all_too_hard_companies(current_user.id, {})
    too_hard_data = []
    for item in all_too_hard_items:
        company_url = url_for('companies.company_dashboard', company_id=item.company_id) if item.company_id else None
        too_hard_data.append({
            'company_name': item.company_name,
            'ticker': item.ticker or '',
            'sector': item.sector or 'N/A',
            'rejection_stage': item.rejection_stage,
            'rejection_stage_label': item.rejection_stage.replace('_', ' ').title(),
            'time_invested': round(item.time_invested_hours, 1),
            'reason': item.reason or '',
            'rejection_date': item.rejection_date.isoformat() if item.rejection_date else None,
            'within_coc': item.within_coc or '',
            'company_id': item.company_id,
            'company_url': company_url,
        })

    # --- Metrics ---
    active_count = len([p for p in active_data if p['status'] == 'active'])
    paused_count = len([p for p in active_data if p['status'] == 'paused'])
    all_projects = current_user.research_projects.all()
    total_time = sum(p.total_hours_spent or 0 for p in all_projects)

    invest_count = sum(1 for p in all_projects if p.decision == 'invest')
    pass_count = sum(1 for p in all_projects if p.decision == 'pass')
    total_decided = invest_count + pass_count
    selectivity_rate = round((pass_count / total_decided) * 100, 1) if total_decided > 0 else 0

    # --- Pipeline (sidebar) ---
    idea_count = IdeaPipeline.query.filter_by(user_id=current_user.id).count()
    total_companies_researched = len(active_data) + len(watchlist_data) + len(too_hard_data) + invest_count
    avg_time = round(total_time / total_companies_researched, 1) if total_companies_researched > 0 else 0
    invest_rate = round((invest_count / total_companies_researched) * 100, 1) if total_companies_researched > 0 else 0

    return render_template('projects_dashboard.html',
                          title="Company Research",
                          active_data=active_data,
                          active_data_json=json.dumps(active_data),
                          watchlist_data=watchlist_data,
                          watchlist_data_json=json.dumps(watchlist_data),
                          too_hard_data=too_hard_data,
                          too_hard_data_json=json.dumps(too_hard_data),
                          metrics={
                              'active_count': active_count,
                              'paused_count': paused_count,
                              'watchlist_count': len(watchlist_data),
                              'too_hard_count': len(too_hard_data),
                              'selectivity_rate': selectivity_rate,
                              'total_time': round(total_time, 1),
                          },
                          pipeline={
                              'idea_count': idea_count,
                              'active_count': active_count + paused_count,
                              'watchlist_count': len(watchlist_data),
                              'passed_count': len(too_hard_data),
                              'invested_count': invest_count,
                          },
                          quick_stats={
                              'total_time': round(total_time, 1),
                              'avg_time': avg_time,
                              'invested_count': invest_count,
                              'invest_rate': invest_rate,
                          })


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
