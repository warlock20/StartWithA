from datetime import timedelta, date
from sqlalchemy import func, and_
from app import db
from app.models import (MistakeLog, WeeklyReview, InvestmentPostMortem,
                       PatternRecognition, LearningPath, DecisionJournal,
                       ResearchProject, IdeaPipeline, JournalEntry,
                       ResearchLog, WorkSession, LearningNote)
import statistics
from app.utils.time_utils import now_utc

def get_weekly_metrics(user_id, week_start):
    """
    Calculate metrics for a specific week.
    """
    week_end = week_start + timedelta(days=6)
    
    # Ideas captured
    ideas_captured = IdeaPipeline.query.filter(
        IdeaPipeline.user_id == user_id,
        IdeaPipeline.created_at >= week_start,
        IdeaPipeline.created_at <= week_end
    ).count()
    
    # Ideas killed
    ideas_killed = IdeaPipeline.query.filter(
        IdeaPipeline.user_id == user_id,
        IdeaPipeline.status == 'killed',
        IdeaPipeline.killed_at >= week_start,
        IdeaPipeline.killed_at <= week_end
    ).count()
    
    # Research hours
    sessions = WorkSession.query.filter(
        WorkSession.user_id == user_id,
        WorkSession.start_time >= week_start,
        WorkSession.start_time <= week_end
    ).all()
    
    total_minutes = sum(s.duration_minutes or 0 for s in sessions)
    research_hours = round(total_minutes / 60, 1)
    
    # Decisions made
    decisions_made = DecisionJournal.query.filter(
        DecisionJournal.user_id == user_id,
        DecisionJournal.decision_date >= week_start,
        DecisionJournal.decision_date <= week_end
    ).count()
    
    return {
        'ideas_captured': ideas_captured,
        'ideas_killed': ideas_killed,
        'research_hours': research_hours,
        'decisions_made': decisions_made
    }

def identify_patterns(user_id):
    """
    Analyze user data to identify patterns.
    """
    patterns = []
    
    # Analyze successful investments
    successful_decisions = DecisionJournal.query.filter(
        DecisionJournal.user_id == user_id,
        DecisionJournal.actual_return > 0
    ).all()
    
    if len(successful_decisions) >= 3:
        # Look for common factors
        success_factors = {}
        for decision in successful_decisions:
            if decision.key_assumptions:
                for assumption in decision.key_assumptions:
                    success_factors[assumption] = success_factors.get(assumption, 0) + 1
        
        # Identify repeated success factors
        for factor, count in success_factors.items():
            if count >= 3:
                pattern = {
                    'name': f'Success Factor: {factor[:50]}',
                    'type': 'success_pattern',
                    'occurrences': count,
                    'description': f'This factor appeared in {count} successful investments'
                }
                patterns.append(pattern)
    
    # Analyze failed investments
    failed_decisions = DecisionJournal.query.filter(
        DecisionJournal.user_id == user_id,
        DecisionJournal.actual_return < 0
    ).all()
    
    if len(failed_decisions) >= 3:
        # Look for common mistakes
        failure_factors = {}
        for decision in failed_decisions:
            if decision.biggest_risks:
                for risk in decision.biggest_risks:
                    if risk in (decision.what_went_wrong or ''):
                        failure_factors[risk] = failure_factors.get(risk, 0) + 1
        
        for factor, count in failure_factors.items():
            if count >= 2:
                pattern = {
                    'name': f'Recurring Risk: {factor[:50]}',
                    'type': 'failure_pattern',
                    'occurrences': count,
                    'description': f'This risk materialized in {count} failed investments'
                }
                patterns.append(pattern)
    
    # Analyze timing patterns
    all_decisions = DecisionJournal.query.filter_by(user_id=user_id).all()
    if len(all_decisions) >= 5:
        # Check if better decisions are made at certain confidence levels
        high_confidence = [d for d in all_decisions if d.confidence_score and d.confidence_score >= 8]
        low_confidence = [d for d in all_decisions if d.confidence_score and d.confidence_score <= 5]
        
        if high_confidence and low_confidence:
            high_success_rate = sum(1 for d in high_confidence if d.actual_return and d.actual_return > 0) / len(high_confidence)
            low_success_rate = sum(1 for d in low_confidence if d.actual_return and d.actual_return > 0) / len(low_confidence)
            
            if high_success_rate > low_success_rate * 1.5:
                pattern = {
                    'name': 'High Confidence Correlation',
                    'type': 'behavioral',
                    'description': 'Your high-confidence decisions perform significantly better',
                    'occurrences': len(high_confidence)
                }
                patterns.append(pattern)
    
    return patterns

def calculate_learning_score(user_id):
    """
    Calculate a learning score based on various factors.
    """
    score = 0
    factors = {}
    
    # Weekly reviews completed
    total_weeks = 12  # Last 12 weeks
    reviews_completed = WeeklyReview.query.filter(
        WeeklyReview.user_id == user_id,
        WeeklyReview.week_start >= now_utc().utcnow().date() - timedelta(weeks=12)
    ).count()
    
    review_score = (reviews_completed / total_weeks) * 20
    score += review_score
    factors['weekly_reviews'] = f'{reviews_completed}/{total_weeks} weeks'
    
    # Mistakes logged and reviewed
    mistakes = MistakeLog.query.filter_by(user_id=user_id).all()
    if mistakes:
        avg_reviews = statistics.mean(m.times_reviewed for m in mistakes)
        mistake_score = min(avg_reviews * 5, 20)
        score += mistake_score
        factors['mistake_reviews'] = f'Avg {avg_reviews:.1f} reviews per mistake'
    
    # Postmortems completed
    decisions_with_outcomes = DecisionJournal.query.filter(
        DecisionJournal.user_id == user_id,
        DecisionJournal.actual_return.isnot(None)
    ).count()
    
    postmortems = InvestmentPostMortem.query.filter_by(user_id=user_id).count()
    
    if decisions_with_outcomes > 0:
        postmortem_rate = postmortems / decisions_with_outcomes
        postmortem_score = postmortem_rate * 20
        score += postmortem_score
        factors['postmortems'] = f'{postmortems}/{decisions_with_outcomes} completed'
    
    # Journal consistency
    last_30_days = now_utc() - timedelta(days=30)
    journal_entries = JournalEntry.query.filter(
        JournalEntry.user_id == user_id,
        JournalEntry.created_at >= last_30_days
    ).count()
    
    journal_score = min(journal_entries * 2, 20)
    score += journal_score
    factors['journal_entries'] = f'{journal_entries} in last 30 days'
    
    # Pattern recognition
    patterns = PatternRecognition.query.filter_by(user_id=user_id).count()
    pattern_score = min(patterns * 4, 20)
    score += pattern_score
    factors['patterns_identified'] = patterns
    
    return {
        'total_score': round(score, 1),
        'max_score': 100,
        'factors': factors,
        'grade': get_grade(score)
    }

def get_grade(score):
    """
    Convert score to letter grade.
    """
    if score >= 90:
        return 'A'
    elif score >= 80:
        return 'B'
    elif score >= 70:
        return 'C'
    elif score >= 60:
        return 'D'
    else:
        return 'F'

def get_review_schedule(user_id):
    """
    Generate a review schedule for the user.
    """
    schedule = []
    today = date.today()
    
    # Weekly review (every Sunday)
    days_until_sunday = (6 - today.weekday()) % 7
    if days_until_sunday == 0:
        days_until_sunday = 7
    next_weekly = today + timedelta(days=days_until_sunday)
    
    schedule.append({
        'type': 'Weekly Review',
        'date': next_weekly,
        'status': 'upcoming',
        'description': 'Review the week\'s activities and learnings'
    })
    
    # Monthly postmortem (first Saturday of each month)
    next_month = today.replace(day=1) + timedelta(days=32)
    next_month = next_month.replace(day=1)
    first_saturday = next_month + timedelta(days=(5 - next_month.weekday()) % 7)
    
    schedule.append({
        'type': 'Monthly Postmortem',
        'date': first_saturday,
        'status': 'upcoming',
        'description': 'Deep review of investment decisions'
    })
    
    # Quarterly pattern review
    quarter_start = today.replace(day=1, month=((today.month - 1) // 3) * 3 + 1)
    next_quarter = quarter_start + timedelta(days=92)
    
    schedule.append({
        'type': 'Quarterly Pattern Review',
        'date': next_quarter,
        'status': 'upcoming',
        'description': 'Identify patterns in your investing behavior'
    })
    
    # Check for overdue reviews
    last_weekly = WeeklyReview.query.filter_by(user_id=user_id)\
                                   .order_by(WeeklyReview.week_start.desc())\
                                   .first()
    
    if last_weekly:
        weeks_since = (today - last_weekly.week_start).days // 7
        if weeks_since > 1:
            schedule.append({
                'type': 'Overdue Weekly Review',
                'date': today,
                'status': 'overdue',
                'description': f'Last review was {weeks_since} weeks ago'
            })
    
    return sorted(schedule, key=lambda x: x['date'])

def generate_learning_recommendations(user_id):
    """
    Generate personalized learning recommendations.
    """
    recommendations = []
    
    # Analyze recent mistakes
    recent_mistakes = MistakeLog.query.filter_by(user_id=user_id)\
                                     .order_by(MistakeLog.created_at.desc())\
                                     .limit(10).all()
    
    if recent_mistakes:
        # Count mistake types
        mistake_types = {}
        for mistake in recent_mistakes:
            mistake_types[mistake.mistake_type] = mistake_types.get(mistake.mistake_type, 0) + 1
        
        # Recommend learning for most common mistake type
        if mistake_types:
            most_common = max(mistake_types, key=mistake_types.get)
            recommendations.append({
                'title': f'Focus on reducing {most_common.replace("_", " ")} errors',
                'description': f'You\'ve made {mistake_types[most_common]} mistakes of this type recently',
                'priority': 'high',
                'action': 'Create a checklist to prevent these errors'
            })
    
    # Check for missing postmortems
    decisions_without_postmortem = db.session.query(DecisionJournal).filter(
        DecisionJournal.user_id == user_id,
        DecisionJournal.actual_return.isnot(None),
        ~DecisionJournal.id.in_(
            db.session.query(InvestmentPostMortem.decision_id).filter(
                InvestmentPostMortem.user_id == user_id,
                InvestmentPostMortem.decision_id.isnot(None)
            )
        )
    ).count()
    
    if decisions_without_postmortem > 0:
        recommendations.append({
            'title': f'Complete {decisions_without_postmortem} investment postmortems',
            'description': 'Learn from your closed positions',
            'priority': 'medium',
            'action': 'Review and document lessons from past investments'
        })
    
    # Suggest pattern review if enough data
    total_decisions = DecisionJournal.query.filter_by(user_id=user_id).count()
    patterns_identified = PatternRecognition.query.filter_by(user_id=user_id).count()
    
    if total_decisions > 10 and patterns_identified < 3:
        recommendations.append({
            'title': 'Identify investment patterns',
            'description': 'You have enough data to identify patterns in your investing',
            'priority': 'medium',
            'action': 'Run a pattern recognition analysis'
        })
    
    # Check learning consistency
    last_learning_note = db.session.query(func.max(LearningNote.created_at))\
                                  .filter_by(user_id=user_id).scalar()
    
    if last_learning_note:
        days_since = (now_utc().utcnow() - last_learning_note).days
        if days_since > 14:
            recommendations.append({
                'title': 'Capture recent learnings',
                'description': f'It\'s been {days_since} days since your last learning note',
                'priority': 'low',
                'action': 'Document any recent insights or lessons'
            })
    
    return recommendations