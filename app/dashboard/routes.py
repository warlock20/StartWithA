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

# In app/dashboard/routes.py
from flask import render_template
from flask_login import current_user, login_required
from app.models import Company, ResearchProject, ResearchSettings, IdeaPipeline, DestinationCheckpoint, PortfolioPosition
from app.services.research_priority import ResearchPriorityService
from app.services.feature_unlock_service import FeatureUnlockService
from app.services.company_state import company_states
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

    # --- Too Hard Basket Rate / Too Hard Total Count ---
    # These two numbers answer different questions and, on purpose, read
    # different data.
    #
    # too_hard_rate asks a PROJECT-level, historical question: "of the
    # companies I took all the way through research to a decision, what
    # fraction did I pass on" -- ResearchProject.decision as it was recorded
    # at decision time, not where the company sits today. It deliberately
    # does NOT go through the ladder, for the same reason all five
    # sector_service.py references stayed unconverted in Task 6: this is a
    # question about a project's own recorded fact, not about company state.
    # Concretely, the ladder's `held` rung sits above `invest_decided` and
    # masks it permanently the moment a company is actually bought -- so a
    # ladder-sourced denominator empties out as investments succeed, and the
    # rate would climb toward 100% precisely *because* things went well
    # (measured on real data: 5 invest decisions, all 5 now `held`, so
    # ladder invest_decided == 0, which drove a wrongly-ladder-scoped
    # version of this rate to 100%). Do not reroute this through
    # company_states -- if a future version of the rate needs to reflect
    # today's state rather than decision history, that is a deliberate,
    # separate design decision, not a "fix" of this comment.
    company_invest_count = current_user.research_projects.filter_by(
        decision='invest'
    ).count()
    company_pass_count = current_user.research_projects.filter_by(
        decision='pass'
    ).count()
    total_decided = company_invest_count + company_pass_count
    too_hard_rate = (company_pass_count / total_decided * 100) if total_decided > 0 else 0

    # too_hard_total_count, unlike the rate above, IS ladder-wide on purpose:
    # it is the total size of the Too Hard Basket, and an idea- or
    # sweep-stage kill belongs in it just as much as a research-stage one.
    # Counting is_dead states here (instead of only
    # ResearchProject.decision == 'pass', which missed idea/sweep kills and
    # research kills recorded as status='killed' or too_hard_reason without
    # decision='pass') is the correct, intended broadening -- do not narrow
    # this to match too_hard_rate above; they are different questions.
    states = company_states(current_user.id)
    too_hard_total_count = sum(1 for s in states.values() if s.is_dead)

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
    tier = current_user.subscription_tier or 'amateur'
    if tier == 'amateur' and not current_user.show_advanced_features:
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
