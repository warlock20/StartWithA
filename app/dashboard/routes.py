# In app/dashboard/routes.py
from flask import render_template
from flask_login import current_user, login_required
from app.models import Company, ResearchSession, ChecklistItem, ResearchAnswer 
from . import dashboard_bp

@dashboard_bp.route('/')
@login_required
def index():
    # --- Calculate Stats ---
    total_companies = Company.query.filter_by(user_id=current_user.id).count()
    favorite_companies_count = current_user.favorites.count()
    
    # Fetch all user sessions once to avoid multiple queries
    all_user_sessions = ResearchSession.query.filter_by(user_id=current_user.id).all()
    total_sessions = len(all_user_sessions)

    # Create the list of completed sessions from the list we just fetched
    completed_sessions_list = [s for s in all_user_sessions if s.status == 'completed']
    completed_sessions_count = len(completed_sessions_list)
    
    in_progress_sessions = total_sessions - completed_sessions_count

    # --- Calculate "Passed" Sessions using the list of completed sessions ---
    # passed_sessions_count = 0
    # for session in completed_sessions_list:
    #     total_items = ChecklistItem.query.filter_by(checklist_id=session.checklist_id).count()
    #     if total_items > 0:
    #         satisfied_answers = ResearchAnswer.query.filter_by(
    #             research_session_id=session.id,
    #             satisfaction_status='satisfied'
    #         ).count()
    #         if total_items == satisfied_answers:
    #             passed_sessions_count += 1
    
    # --- Fetch Recent Activity ---
    # We can reuse the all_user_sessions list if it's already sorted by date,
    # but a new query with .limit(5) is more efficient and clearer.
    recent_sessions = ResearchSession.query.filter_by(user_id=current_user.id)\
                                         .order_by(ResearchSession.start_date.desc())\
                                         .limit(5).all()

    # --- Render Template with ALL necessary variables ---
    return render_template(
        'dashboard.html',
        title='Dashboard',
        total_companies=total_companies,
        total_sessions=total_sessions,
        completed_sessions=completed_sessions_count,
        in_progress_sessions=in_progress_sessions,
        favorite_companies_count=favorite_companies_count,
        passed_sessions_count=passed_sessions_count, # Now included
        recent_sessions=recent_sessions
    )