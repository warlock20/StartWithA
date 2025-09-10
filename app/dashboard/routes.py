# In app/dashboard/routes.py
from flask import render_template
from flask_login import current_user, login_required
from app.models import Company, ResearchProject, IdeaPipeline, DestinationCheckpoint
from . import dashboard_bp
from datetime import datetime, timedelta

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

    # Get the next 5 upcoming checkpoints in the next 90 days
    today = datetime.utcnow().date()
    ninety_days_from_now = today + timedelta(days=90)
    upcoming_checkpoints = DestinationCheckpoint.query.filter(
        DestinationCheckpoint.user_id == current_user.id,
        DestinationCheckpoint.target_date >= today,
        DestinationCheckpoint.target_date <= ninety_days_from_now
    ).order_by(DestinationCheckpoint.target_date.asc()).limit(5).all()


    return render_template(
        'dashboard.html',
        title='Dashboard',
        inbox_count=inbox_count,
        active_projects_count=len(active_projects),
        active_projects_list=active_projects,
        portfolio_count=portfolio_count,
        upcoming_checkpoints=upcoming_checkpoints
    )

@dashboard_bp.route('/portfolio_timeline')
@login_required
def portfolio_timeline():
    # This route remains the same
    portfolio_company_ids = [
        c.id for c in Company.query.filter_by(user_id=current_user.id, is_in_portfolio=True).all()
    ]
    checkpoints = []
    if portfolio_company_ids:
        checkpoints = DestinationCheckpoint.query.filter(
            DestinationCheckpoint.company_id.in_(portfolio_company_ids)
        ).order_by(DestinationCheckpoint.target_date.asc()).all()
    return render_template(
        'portfolio_timeline.html',
        title="Portfolio Checkpoints Timeline",
        checkpoints=checkpoints
    )