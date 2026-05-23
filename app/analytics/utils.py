from datetime import timedelta, timezone
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from app import db
from app.models import (User, ResearchMetrics, IdeaPipeline, ResearchProject,
                       WorkSession, ResearchLog, IdeaSourceAnalysis)
from app.utils.time_utils import now_utc

def update_user_metrics(user_id):
    """
    Update aggregated metrics for a user.
    This should be called periodically or after significant events.
    """
    user = User.query.get(user_id)
    if not user:
        return None
    
    # Get or create metrics record
    metrics = ResearchMetrics.query.filter_by(user_id=user_id).first()
    if not metrics:
        metrics = ResearchMetrics(user_id=user_id)
        db.session.add(metrics)
    elif metrics.last_updated and (now_utc() - metrics.last_updated.replace(tzinfo=timezone.utc)).total_seconds() < 900:
        # Skip recomputation if updated within 15 minutes
        return metrics

    # Update idea pipeline metrics
    metrics.total_ideas_captured = user.idea_pipeline.count()
    metrics.ideas_killed = user.idea_pipeline.filter_by(status='killed').count()
    metrics.ideas_promoted = user.idea_pipeline.filter_by(status='promoted').count()
    metrics.ideas_in_pipeline = user.idea_pipeline.filter_by(status='inbox').count()
    
    # Calculate kill rate
    if metrics.total_ideas_captured > 0:
        metrics.kill_rate = (metrics.ideas_killed / metrics.total_ideas_captured) * 100
    
    # Calculate average days to decision
    decided_ideas = user.idea_pipeline.filter(
        IdeaPipeline.status.in_(['killed', 'promoted'])
    ).all()
    
    if decided_ideas:
        total_days = 0
        count = 0
        for idea in decided_ideas:
            if idea.status == 'killed' and idea.killed_at:
                days = (idea.killed_at - idea.created_at).days
            elif idea.status == 'promoted' and idea.promoted_at:
                days = (idea.promoted_at - idea.created_at).days
            else:
                continue
            total_days += days
            count += 1
        
        if count > 0:
            metrics.average_days_to_decision = total_days / count
    
    # Update research time metrics
    total_minutes = db.session.query(func.sum(WorkSession.duration_minutes))\
                              .filter_by(user_id=user_id).scalar() or 0
    metrics.total_research_hours = total_minutes / 60
    
    # Average hours per company
    companies_researched = user.research_projects.distinct(ResearchProject.company_id).count()
    if companies_researched > 0:
        metrics.average_hours_per_company = metrics.total_research_hours / companies_researched
    
    # Decision metrics
    completed_projects = user.research_projects.filter_by(status='completed').all()
    metrics.total_investment_decisions = len(completed_projects)
    metrics.invest_decisions = sum(1 for p in completed_projects if p.decision == 'invest')
    metrics.pass_decisions = sum(1 for p in completed_projects if p.decision == 'pass')
    
    # Average confidence
    confidence_scores = [p.decision_confidence for p in completed_projects 
                        if p.decision_confidence]
    if confidence_scores:
        metrics.average_confidence_score = sum(confidence_scores) / len(confidence_scores)
    
    # Find most time-consuming step
    step_times = {}
    for project in user.research_projects.all():
        if project.time_per_step:
            for step_index, minutes in project.time_per_step.items():
                step = project.get_step(int(step_index))
                if step:
                    step_name = step['name']
                    step_times[step_name] = step_times.get(step_name, 0) + minutes
    
    if step_times:
        metrics.most_time_consuming_step = max(step_times, key=step_times.get)
    
    # Behavioral patterns from research logs
    recent_logs = user.research_logs.filter(
        ResearchLog.timestamp >= now_utc() - timedelta(days=90)
    ).all()
    
    if recent_logs:
        # Most productive day
        day_counts = {}
        hour_counts = {}
        for log in recent_logs:
            if log.day_of_week is not None:
                day_counts[log.day_of_week] = day_counts.get(log.day_of_week, 0) + 1
            if log.hour_of_day is not None:
                hour_counts[log.hour_of_day] = hour_counts.get(log.hour_of_day, 0) + 1
        
        if day_counts:
            best_day = max(day_counts, key=day_counts.get)
            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            metrics.most_productive_day = days[best_day]
        
        if hour_counts:
            metrics.most_productive_hour = max(hour_counts, key=hour_counts.get)
    
    # Research streak
    latest_log = user.research_logs.order_by(ResearchLog.timestamp.desc()).first()
    if latest_log:
        metrics.last_research_date = latest_log.timestamp.date()
        
        # Calculate streak (single query instead of one per day)
        streak = 0
        current_date = now_utc().date()
        log_dates = {
            d for d, in db.session.query(func.date(ResearchLog.timestamp))
            .filter(ResearchLog.user_id == user_id)
            .distinct().all()
        }
        while current_date in log_dates:
            streak += 1
            current_date -= timedelta(days=1)
        metrics.research_streak_days = streak
    
    metrics.last_updated = now_utc()
    
    try:
        db.session.commit()
        return metrics
    except Exception as e:
        db.session.rollback()
        print(f"Error updating metrics: {e}")
        return None

def log_research_activity(user_id, activity_type, **kwargs):
    """
    Log a research activity for analysis.
    """
    now = now_utc()
    log = ResearchLog(
        user_id=user_id,
        activity_type=activity_type,
        timestamp=now,
        day_of_week=now.weekday(),
        hour_of_day=now.hour,
        details=kwargs.get('details', {}),
        idea_id=kwargs.get('idea_id'),
        company_id=kwargs.get('company_id'),
        project_id=kwargs.get('project_id'),
        duration_minutes=kwargs.get('duration_minutes')
    )
    
    db.session.add(log)
    
    try:
        db.session.commit()
        return log
    except Exception as e:
        db.session.rollback()
        print(f"Error logging activity: {e}")
        return None

def analyze_idea_sources(user_id):
    """
    Analyze the quality of different idea sources.
    """
    user = User.query.get(user_id)
    if not user:
        return []
    
    # Get all unique sources
    sources = db.session.query(IdeaPipeline.source)\
                       .filter_by(user_id=user_id)\
                       .filter(IdeaPipeline.source.isnot(None))\
                       .distinct().all()
    
    analyses = []
    for (source,) in sources:
        # Get or create analysis record
        analysis = IdeaSourceAnalysis.query.filter_by(
            user_id=user_id,
            source_name=source
        ).first()
        
        if not analysis:
            analysis = IdeaSourceAnalysis(
                user_id=user_id,
                source_name=source
            )
            db.session.add(analysis)
        
        # Calculate metrics
        source_ideas = user.idea_pipeline.filter_by(source=source).all()
        analysis.total_ideas = len(source_ideas)
        analysis.ideas_killed = sum(1 for i in source_ideas if i.status == 'killed')
        analysis.ideas_promoted = sum(1 for i in source_ideas if i.status == 'promoted')
        
        if analysis.total_ideas > 0:
            analysis.survival_rate = (analysis.ideas_promoted / analysis.total_ideas) * 100
        
        # Track investments from promoted ideas (batch query)
        promoted_company_ids = [
            idea.promoted_to_company_id for idea in source_ideas
            if idea.promoted_to_company_id
        ]
        invested_count = 0
        if promoted_company_ids:
            invested_company_ids = {
                r[0] for r in db.session.query(ResearchProject.company_id)
                .filter(
                    ResearchProject.company_id.in_(promoted_company_ids),
                    ResearchProject.decision == 'invest'
                ).all()
            }
            invested_count = sum(
                1 for cid in promoted_company_ids if cid in invested_company_ids
            )
        
        analysis.ideas_invested = invested_count
        if analysis.total_ideas > 0:
            analysis.investment_rate = (invested_count / analysis.total_ideas) * 100
        
        # Update last idea date
        latest_idea = user.idea_pipeline.filter_by(source=source)\
                                       .order_by(IdeaPipeline.created_at.desc())\
                                       .first()
        if latest_idea:
            analysis.last_idea_date = latest_idea.created_at
        
        analyses.append(analysis)
    
    try:
        db.session.commit()
        return analyses
    except Exception as e:
        db.session.rollback()
        print(f"Error analyzing sources: {e}")
        return []

def get_time_allocation_data(user_id, days=30):
    """
    Get time allocation data for the past N days.
    """
    cutoff_date = now_utc() - timedelta(days=days)

    # Get work sessions (eager load project + company to avoid N+1)
    sessions = WorkSession.query.filter(
        WorkSession.user_id == user_id,
        WorkSession.start_time >= cutoff_date
    ).options(
        joinedload(WorkSession.project).joinedload(ResearchProject.company)
    ).all()
    
    # Aggregate by step type
    time_by_type = {}
    time_by_company = {}
    time_by_day = {}
    
    for session in sessions:
        # By step type
        if session.step_name:
            time_by_type[session.step_name] = time_by_type.get(session.step_name, 0) + (session.duration_minutes or 0)
        
        # By company
        if session.project and session.project.company:
            company_name = session.project.company.name
            time_by_company[company_name] = time_by_company.get(company_name, 0) + (session.duration_minutes or 0)
        
        # By day
        if session.start_time:
            day = session.start_time.date()
            time_by_day[day] = time_by_day.get(day, 0) + (session.duration_minutes or 0)
    
    return {
        'by_type': time_by_type,
        'by_company': time_by_company,
        'by_day': time_by_day,
        'total_minutes': sum(s.duration_minutes or 0 for s in sessions)
    }