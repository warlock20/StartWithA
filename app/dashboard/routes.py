# In app/dashboard/routes.py
from flask import render_template
from flask_login import current_user, login_required
from app.models import Company, ResearchSession, ChecklistItem, ResearchAnswer, DestinationCheckpoint
from . import dashboard_bp
from sqlalchemy import func
from app import db
from app.companies.routes import get_company_market_data

@dashboard_bp.route('/')
@login_required
def index():
    # --- Calculate All Stats ---

    # Basic counts
    total_companies = Company.query.filter_by(user_id=current_user.id).count()
    favorite_companies_count = current_user.favorites.count()
    
    # Session-based counts
    all_user_sessions = ResearchSession.query.filter_by(user_id=current_user.id).all()
    total_sessions = len(all_user_sessions)
    completed_sessions_list = [s for s in all_user_sessions if s.status == 'completed']
    completed_sessions_count = len(completed_sessions_list)
    in_progress_sessions = total_sessions - completed_sessions_count

    # "Passed" Sessions calculation (this is the part that was missing)
    passed_sessions_count = 0
    for session in completed_sessions_list:
        total_items = ChecklistItem.query.filter_by(checklist_id=session.checklist_id).count()
        if total_items > 0:
            satisfied_answers = ResearchAnswer.query.filter_by(
                research_session_id=session.id,
                satisfaction_status='satisfied'
            ).count()
            if total_items == satisfied_answers:
                passed_sessions_count += 1
    
    # Data for Sector Pie Chart
    sector_data_query = db.session.query(
        Company.sector, 
        func.count(Company.id)
    ).filter(Company.user_id == current_user.id).group_by(Company.sector).order_by(func.count(Company.id).desc()).all()
    sector_labels = [row[0] if row[0] else "Uncategorized" for row in sector_data_query]
    sector_values = [row[1] for row in sector_data_query]

    # --- Fetch Recent Activity ---
    recent_sessions = ResearchSession.query.filter_by(user_id=current_user.id)\
                                         .order_by(ResearchSession.start_date.desc())\
                                         .limit(5).all()
    # Prepare data for the Margin of Safety Bar chart
    favorite_companies = current_user.favorites.all()
    mos_data = [] # Margin of Safety data

    for company in favorite_companies:
        market_data = get_company_market_data(company.ticker_symbol)
        if market_data and market_data.get('marketCap') and company.intrinsic_value:
            market_cap = market_data.get('marketCap')
            # Calculate Margin of Safety
            margin = ((market_cap - company.intrinsic_value) / market_cap) * 100
            mos_data.append({
                'name': company.ticker_symbol, # Use ticker for concise labels
                'mos': round(margin, 2)
            })

    # Sort the data to show the most undervalued (largest negative MoS) first
    mos_data.sort(key=lambda x: x['mos'])

    # Prepare separate lists for Chart.js
    mos_labels = [d['name'] for d in mos_data]
    mos_values = [d['mos'] for d in mos_data]                                     

    # --- Render Template with ALL variables ---
    return render_template(
        'dashboard.html',
        title='Dashboard',
        total_companies=total_companies,
        total_sessions=total_sessions,
        completed_sessions=completed_sessions_count,
        in_progress_sessions=in_progress_sessions,
        favorite_companies_count=favorite_companies_count,
        passed_sessions_count=passed_sessions_count, # Now correctly calculated and passed
        recent_sessions=recent_sessions,
        sector_labels=sector_labels,
        sector_values=sector_values,
        mos_labels=mos_labels,
        mos_values=mos_values
    )
    
@dashboard_bp.route('/portfolio_timeline')
@login_required
def portfolio_timeline():
    # Get IDs of all companies in the user's portfolio
    portfolio_company_ids = [
        c.id for c in Company.query.filter_by(user_id=current_user.id, is_in_portfolio=True).all()
    ]

    # Fetch all checkpoints for those companies, ordered by target date
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