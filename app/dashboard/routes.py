# In app/dashboard/routes.py
from flask import render_template
from flask_login import current_user, login_required
from app.models import Company, ResearchProject, IdeaPipeline, DestinationCheckpoint, Checklist, KillChecklist, ResearchTemplate
from app.services.too_hard_service import TooHardBasketService
from app.services.research_priority import ResearchPriorityService
from . import dashboard_bp
from datetime import datetime, timedelta
from app.utils.time_utils import now_utc, ensure_timezone_aware

@dashboard_bp.route('/')
@login_required
def index():
    # --- Fetch Actionable Data ---

    # Get the count of ideas waiting for review (includes inbox and ideas being evaluated)
    inbox_count = current_user.idea_pipeline.filter(
        IdeaPipeline.status.in_(['inbox', 'killing'])
    ).count()

    # Get prioritized research recommendation
    focus_recommendation = ResearchPriorityService.get_focus_recommendation(current_user)
    active_projects = [s.project for s in ([focus_recommendation.hero] + focus_recommendation.runners_up) if s]

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

    # Get portfolio company IDs for the current user (IDs only, no full objects)
    portfolio_company_ids = [
        cid for (cid,) in Company.query.filter_by(
            user_id=current_user.id, is_in_portfolio=True
        ).with_entities(Company.id).all()
    ]

    upcoming_checkpoints = []
    if portfolio_company_ids:
        # Filter by date and status
        upcoming_checkpoints = DestinationCheckpoint.query.filter(
            DestinationCheckpoint.company_id.in_(portfolio_company_ids),
            DestinationCheckpoint.target_date >= today,
            DestinationCheckpoint.target_date <= twelve_months_from_now,
            DestinationCheckpoint.status == 'Active'  # Only show active checkpoints
        ).order_by(DestinationCheckpoint.target_date.asc()).limit(5).all()

    # Too Hard Basket stats via SQL COUNT (no objects loaded into memory)
    early_kills_count = IdeaPipeline.query.filter_by(
        user_id=current_user.id, status='killed'
    ).count()

    mid_research_count = ResearchProject.query.filter(
        ResearchProject.user_id == current_user.id,
        ResearchProject.decision == 'pass',
        ResearchProject.too_hard_reason.isnot(None)
    ).count()

    deep_analysis_count = ResearchProject.query.filter(
        ResearchProject.user_id == current_user.id,
        ResearchProject.decision == 'pass',
        ResearchProject.too_hard_reason.is_(None)
    ).count()

    too_hard_total_count = early_kills_count + mid_research_count + deep_analysis_count

    # Recent rejections (last 30 days) via SQL
    thirty_days_ago = now_utc() - timedelta(days=30)
    recent_kills = IdeaPipeline.query.filter(
        IdeaPipeline.user_id == current_user.id,
        IdeaPipeline.status == 'killed',
        IdeaPipeline.killed_at >= thirty_days_ago
    ).count()
    recent_passes = ResearchProject.query.filter(
        ResearchProject.user_id == current_user.id,
        ResearchProject.decision == 'pass',
        ResearchProject.decision_date >= thirty_days_ago
    ).count()
    recent_rejections_count = recent_kills + recent_passes

    # Get analytics and recommendations (cached 5 min)
    analytics_data = TooHardBasketService.get_analytics(current_user.id)
    recommendations = analytics_data.get('recommendations', [])

    return render_template(
        'dashboard.html',
        title='Dashboard',
        focus_recommendation=focus_recommendation,
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

