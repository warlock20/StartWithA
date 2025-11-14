# In app/dashboard/routes.py
from flask import render_template
from flask_login import current_user, login_required
from app.models import Company, ResearchProject, IdeaPipeline, DestinationCheckpoint, Checklist, KillChecklist, ResearchTemplate
from app.services.too_hard_service import TooHardBasketService
from . import dashboard_bp
from datetime import datetime, timedelta
from app.utils.time_utils import now_utc, ensure_timezone_aware

@dashboard_bp.route('/')
@login_required
def index():
    # --- Fetch Actionable Data ---

    # Get the count of ideas waiting for review
    inbox_count = current_user.idea_pipeline.filter_by(status='inbox').count()

    # Get the top 5 active research projects
    active_projects = current_user.research_projects.filter_by(status='active')\
                                                    .order_by(ResearchProject.last_worked_at.desc())\
                                                    .limit(5).all()

    # Get the number of companies in the active portfolio
    portfolio_count = current_user.companies.filter_by(is_in_portfolio=True).count()

    # Calculate Too Hard Basket Rate (Filter Rate Metric)
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

    # Get user's research templates and kill checklists
    user_templates = current_user.research_templates.filter_by(is_active=True).order_by(ResearchTemplate.times_used.desc()).all()
    user_kill_checklists = current_user.kill_checklists.order_by(KillChecklist.created_at.desc()).all()
    legacy_checklists = current_user.checklists.order_by(Checklist.id.desc()).all()
    
    template_count = len(user_templates)
    kill_checklist_count = len(user_kill_checklists)
    legacy_checklist_count = len(legacy_checklists)

    # Get the next 5 upcoming checkpoints in the next 12 months for PORTFOLIO companies only
    # Extended timeframe for thesis validation (90 days was too restrictive)
    today = now_utc().date()
    twelve_months_from_now = today + timedelta(days=365)

    # Get portfolio company IDs for the current user
    portfolio_company_ids = [
        c.id for c in Company.query.filter_by(user_id=current_user.id, is_in_portfolio=True).all()
    ]

    upcoming_checkpoints = []
    if portfolio_company_ids:
        # Debug: Print some information
        print(f"DEBUG: Found {len(portfolio_company_ids)} portfolio companies: {portfolio_company_ids}")

        # First, let's see all checkpoints for portfolio companies
        all_portfolio_checkpoints = DestinationCheckpoint.query.filter(
            DestinationCheckpoint.company_id.in_(portfolio_company_ids)
        ).all()
        print(f"DEBUG: Found {len(all_portfolio_checkpoints)} total checkpoints for portfolio companies")
        print(f"DEBUG: Date range: {today} to {twelve_months_from_now}")

        for cp in all_portfolio_checkpoints:
            print(f"DEBUG: Checkpoint details - Company: {cp.company.name}, Metric: {cp.metric}, Date: {cp.target_date}, Status: '{cp.status}', In date range: {today <= cp.target_date <= twelve_months_from_now}")

        # Now filter by date and status
        upcoming_checkpoints = DestinationCheckpoint.query.filter(
            DestinationCheckpoint.company_id.in_(portfolio_company_ids),
            DestinationCheckpoint.target_date >= today,
            DestinationCheckpoint.target_date <= twelve_months_from_now,
            DestinationCheckpoint.status == 'Active'  # Only show active checkpoints
        ).order_by(DestinationCheckpoint.target_date.asc()).limit(5).all()

        print(f"DEBUG: Found {len(upcoming_checkpoints)} upcoming active checkpoints")
        for cp in upcoming_checkpoints:
            print(f"DEBUG: Checkpoint - {cp.company.name}: {cp.metric} on {cp.target_date} (status: {cp.status})")
    else:
        print("DEBUG: No portfolio companies found")

    # Get Too Hard Basket statistics
    all_too_hard_items = TooHardBasketService.get_all_too_hard_companies(current_user.id, {})
    too_hard_total_count = len(all_too_hard_items)

    # Calculate recent rejections (last 30 days)
    thirty_days_ago = now_utc() - timedelta(days=30)
    recent_rejections = [
        item for item in all_too_hard_items
        if item.rejection_date and ensure_timezone_aware(item.rejection_date) >= thirty_days_ago
    ]
    recent_rejections_count = len(recent_rejections)

    # Count by stage
    early_kills_count = sum(1 for item in all_too_hard_items if item.rejection_stage == 'kill_checklist')
    mid_research_count = sum(1 for item in all_too_hard_items if item.rejection_stage == 'mid_research')
    deep_analysis_count = sum(1 for item in all_too_hard_items if item.rejection_stage == 'full_analysis')

    # Get analytics and recommendations
    analytics_data = TooHardBasketService.get_analytics(current_user.id)
    recommendations = analytics_data.get('recommendations', [])

    return render_template(
        'dashboard.html',
        title='Dashboard',
        inbox_count=inbox_count,
        active_projects_count=len(active_projects),
        active_projects_list=active_projects,
        portfolio_count=portfolio_count,
        upcoming_checkpoints=upcoming_checkpoints,
        user_templates=user_templates,
        user_kill_checklists=user_kill_checklists,
        legacy_checklists=legacy_checklists,
        template_count=template_count,
        kill_checklist_count=kill_checklist_count,
        legacy_checklist_count=legacy_checklist_count,
        too_hard_rate=round(too_hard_rate, 1),
        total_decided_companies=total_decided_companies,
        company_invest_count=company_invest_count,
        company_pass_count=company_pass_count,
        too_hard_total_count=too_hard_total_count,
        recent_rejections_count=recent_rejections_count,
        early_kills_count=early_kills_count,
        mid_research_count=mid_research_count,
        deep_analysis_count=deep_analysis_count,
        recommendations=recommendations
    )

