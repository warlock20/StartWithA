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

from datetime import timedelta, date
from sqlalchemy import func, and_
from app import db
from app.models import (MistakeLog, InvestmentPostMortem,
                       PatternRecognition, DecisionJournal,
                       JournalEntry, LearningNote)
import statistics
from app.utils.time_utils import now_utc

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