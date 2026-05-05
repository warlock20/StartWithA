# In app/dashboard/routes.py
from flask import render_template
from flask_login import current_user, login_required
from app.models import Company, ResearchProject, ResearchSettings, IdeaPipeline, DestinationCheckpoint, PortfolioPosition
from app.services.research_priority import ResearchPriorityService
from app.services.feature_unlock_service import FeatureUnlockService
from . import dashboard_bp
from datetime import timedelta
from app.utils.time_utils import now_utc


@dashboard_bp.route('/')
@login_required
def index():
    # --- Inbox ---
    inbox_count = current_user.idea_pipeline.filter(
        IdeaPipeline.status.in_(['inbox', 'killing'])
    ).count()

    # --- Research Focus ---
    research_settings = ResearchSettings.get_or_create(current_user.id)
    pinned_project_id = research_settings.pinned_project_id
    focus_recommendation = ResearchPriorityService.get_focus_recommendation(current_user)
    all_scored = [focus_recommendation.hero] + focus_recommendation.runners_up if focus_recommendation.hero else list(focus_recommendation.runners_up)
    all_scored = [s for s in all_scored if s]
    active_projects = [s.project for s in all_scored]

    # Stale projects for "Needs Attention" panel (idle >= 10 days)
    stale_projects = [s for s in all_scored if s.days_idle >= 10 and s.is_stale_warning]

    # --- Portfolio Position Count (active positions, not companies) ---
    position_count = PortfolioPosition.query.filter_by(
        user_id=current_user.id, is_active=True
    ).count()

    # --- Too Hard Basket Rate ---
    company_invest_count = current_user.research_projects.filter_by(
        decision='invest'
    ).count()

    company_pass_count = current_user.research_projects.filter_by(
        decision='pass'
    ).count()

    total_decided = company_invest_count + company_pass_count
    too_hard_rate = (company_pass_count / total_decided * 100) if total_decided > 0 else 0

    # --- Too Hard Total Count ---
    early_kills_count = IdeaPipeline.query.filter_by(
        user_id=current_user.id, status='killed'
    ).count()

    research_pass_count = ResearchProject.query.filter(
        ResearchProject.user_id == current_user.id,
        ResearchProject.decision == 'pass',
    ).count()

    too_hard_total_count = early_kills_count + research_pass_count

    # --- Upcoming Checkpoints ---
    today = now_utc().date()
    twelve_months = today + timedelta(days=365)

    portfolio_company_ids = [
        cid for (cid,) in Company.query.filter_by(
            user_id=current_user.id, is_in_portfolio=True
        ).with_entities(Company.id).all()
    ]

    upcoming_checkpoints = []
    if portfolio_company_ids:
        upcoming_checkpoints = DestinationCheckpoint.query.filter(
            DestinationCheckpoint.company_id.in_(portfolio_company_ids),
            DestinationCheckpoint.target_date >= today,
            DestinationCheckpoint.target_date <= twelve_months,
            DestinationCheckpoint.status == 'Active'
        ).order_by(DestinationCheckpoint.target_date.asc()).limit(5).all()

    # --- Unlock Progress (free-tier users only) ---
    unlock_progress = []
    tier = current_user.subscription_tier or 'free'
    if tier == 'free' and not current_user.show_advanced_features:
        unlock_progress = FeatureUnlockService.get_unlock_progress(current_user)

    return render_template(
        'dashboard.html',
        title='Dashboard',
        # Pipeline strip
        inbox_count=inbox_count,
        active_projects_count=len(active_projects),
        position_count=position_count,
        too_hard_total_count=too_hard_total_count,
        too_hard_rate=round(too_hard_rate, 1),
        # Research focus
        focus_recommendation=focus_recommendation,
        pinned_project_id=pinned_project_id,
        active_projects_list=active_projects,
        all_scored_projects=all_scored,
        # Action items
        upcoming_checkpoints=upcoming_checkpoints,
        stale_projects=stale_projects,
        # Feature unlocks
        unlock_progress=unlock_progress,
        # Legacy (kept for template compatibility)
        company_invest_count=company_invest_count,
    )
