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

"""
Dynamic Kill Checklist Analytics Service

This service provides intelligent analysis and optimization suggestions for Kill Checklists
based on historical usage patterns, effectiveness metrics, and mistake log integration.
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from app import db
from app.models import KillChecklist, KillCriterion, KillSession, KillChecklistSuggestion
from typing import List, Optional


class KillChecklistAnalytics:
    """Core analytics engine for Dynamic Kill Checklist optimization"""

    @staticmethod
    def calculate_criterion_effectiveness(criterion_id: int, days_back: int = 90) -> float:
        """
        Calculate effectiveness score for a kill criterion.

        Effectiveness = (Success Rate × Usage Frequency × Position Weight × Recency Factor)

        Args:
            criterion_id: ID of the criterion to analyze
            days_back: Number of days of history to consider

        Returns:
            Effectiveness score (0.0 to 1.0)
        """
        criterion = KillCriterion.query.get(criterion_id)
        if not criterion:
            return 0.0

        # Basic effectiveness metrics
        if criterion.times_evaluated == 0:
            return 0.0

        success_rate = criterion.times_failed / criterion.times_evaluated

        # Usage frequency (how often this criterion is actually triggered)
        total_evaluations = KillChecklistAnalytics._get_total_evaluations(
            criterion.kill_checklist_id, days_back
        )
        usage_frequency = criterion.times_evaluated / max(total_evaluations, 1)

        # Position weight (earlier criteria get higher weight)
        total_criteria = criterion.kill_checklist.criteria.count()
        position_weight = (total_criteria - criterion.order + 1) / total_criteria

        # Recency factor (more recent usage gets higher weight)
        recency_factor = KillChecklistAnalytics._calculate_recency_factor(
            criterion.last_used, days_back
        )

        # Final effectiveness score
        effectiveness = success_rate * usage_frequency * position_weight * recency_factor

        # Update the criterion with the new score
        criterion.effectiveness_score = effectiveness
        criterion.last_calculated = datetime.now(timezone.utc)

        return effectiveness

    @staticmethod
    def suggest_reordering(checklist_id: int) -> Optional[KillChecklistSuggestion]:
        """
        Analyze checklist and suggest optimal criterion ordering based on effectiveness.

        Args:
            checklist_id: ID of the checklist to analyze

        Returns:
            KillChecklistSuggestion object or None if no improvement possible
        """
        checklist = KillChecklist.query.get(checklist_id)
        if not checklist:
            return None

        # Get all criteria with their effectiveness scores
        criteria = list(checklist.criteria.order_by(KillCriterion.order))

        if len(criteria) < 2:
            return None  # No point in reordering with less than 2 criteria

        # Calculate effectiveness scores for all criteria
        for criterion in criteria:
            KillChecklistAnalytics.calculate_criterion_effectiveness(criterion.id)

        # Sort by effectiveness score (descending)
        optimal_order = sorted(criteria, key=lambda c: c.effectiveness_score, reverse=True)

        # Check if current order is already optimal
        current_order = [c.id for c in criteria]
        optimal_ids = [c.id for c in optimal_order]

        if current_order == optimal_ids:
            return None  # Already optimally ordered

        # Calculate potential improvement
        current_avg_effectiveness = sum(c.effectiveness_score for c in criteria) / len(criteria)

        # Simulate new effectiveness with optimal ordering
        improvement_estimate = KillChecklistAnalytics._estimate_reorder_improvement(
            criteria, optimal_order
        )

        if improvement_estimate < 0.05:  # Less than 5% improvement
            return None

        # Create suggestion
        suggestion_data = {
            "current_order": [{"id": c.id, "question": c.question, "position": c.order} for c in criteria],
            "optimal_order": [{"id": c.id, "question": c.question, "new_position": i+1,
                             "effectiveness": c.effectiveness_score} for i, c in enumerate(optimal_order)],
            "improvement_estimate": improvement_estimate
        }

        suggestion = KillChecklistSuggestion(
            user_id=checklist.user_id,
            kill_checklist_id=checklist_id,
            suggestion_type='reorder_criteria',
            title=f"Optimize '{checklist.name}' criterion order",
            description=f"Reordering criteria by effectiveness could improve your kill rate by {improvement_estimate:.1%}",
            reasoning=f"Analysis shows that '{optimal_order[0].question[:50]}...' is your most effective criterion but currently at position {optimal_order[0].order}. Moving high-effectiveness criteria earlier saves evaluation time.",
            suggestion_data=suggestion_data,
            effectiveness_gain=improvement_estimate,
            confidence_score=KillChecklistAnalytics._calculate_confidence_score(criteria),
            trigger_event='evaluation_milestone',
            source_data={"total_evaluations": checklist.total_ideas_evaluated}
        )

        return suggestion

    # Private helper methods

    @staticmethod
    def _get_total_evaluations(checklist_id: int, days_back: int) -> int:
        """Get total number of evaluations for a checklist in the given period"""
        since_date = datetime.now(timezone.utc) - timedelta(days=days_back)

        return db.session.query(func.count(KillSession.id))\
            .filter(KillSession.kill_checklist_id == checklist_id)\
            .filter(KillSession.started_at >= since_date)\
            .scalar() or 0

    @staticmethod
    def _calculate_recency_factor(last_used: Optional[datetime], days_back: int) -> float:
        """Calculate recency factor for effectiveness scoring"""
        if not last_used:
            return 0.5  # Default for never-used criteria

        days_since_used = (datetime.now(timezone.utc) - last_used).days

        if days_since_used > days_back:
            return 0.1  # Very old usage
        elif days_since_used > days_back / 2:
            return 0.5  # Somewhat recent
        else:
            return 1.0  # Recent usage

    @staticmethod
    def _estimate_reorder_improvement(current_criteria: List, optimal_order: List) -> float:
        """Estimate the improvement from reordering criteria"""
        # Simple heuristic: improvement based on how much high-effectiveness criteria move up
        improvement = 0.0

        for i, optimal_criterion in enumerate(optimal_order[:3]):  # Focus on top 3
            current_pos = next((j for j, c in enumerate(current_criteria) if c.id == optimal_criterion.id), i)
            if i < current_pos:  # Moving up in the order
                position_improvement = (current_pos - i) / len(current_criteria)
                effectiveness_weight = optimal_criterion.effectiveness_score
                improvement += position_improvement * effectiveness_weight

        return min(improvement, 0.3)  # Cap at 30% improvement

    @staticmethod
    def _calculate_confidence_score(criteria: List) -> float:
        """Calculate confidence score for suggestions based on data quality"""
        total_evaluations = sum(c.times_evaluated for c in criteria)

        if total_evaluations < 10:
            return 0.3  # Low confidence
        elif total_evaluations < 50:
            return 0.6  # Medium confidence
        else:
            return 0.9  # High confidence

    @staticmethod
    def _suggest_cleanup(checklist_id: int) -> List[KillChecklistSuggestion]:
        """Suggest removing or modifying underperforming criteria"""
        suggestions = []
        checklist = KillChecklist.query.get(checklist_id)

        if not checklist:
            return suggestions

        # Find criteria that are never triggered or have very low effectiveness
        criteria = checklist.criteria.all()

        for criterion in criteria:
            if criterion.times_evaluated > 20 and criterion.effectiveness_score < 0.1:
                # Suggest removing ineffective criteria
                suggestion = KillChecklistSuggestion(
                    user_id=checklist.user_id,
                    kill_checklist_id=checklist_id,
                    suggestion_type='remove_criterion',
                    title=f"Remove underperforming criterion",
                    description=f"'{criterion.question[:50]}...' has low effectiveness (kills {criterion.failure_rate:.1f}% of ideas)",
                    reasoning="This criterion rarely eliminates ideas and may be adding unnecessary complexity to your process.",
                    suggestion_data={"criterion_id": criterion.id, "effectiveness": criterion.effectiveness_score},
                    effectiveness_gain=0.02,  # Small gain from removing noise
                    confidence_score=0.8,
                    trigger_event='periodic_analysis'
                )
                suggestions.append(suggestion)

        return suggestions

class SuggestionEngine:
    """High-level suggestion generation and management"""

    @staticmethod
    def process_evaluation_milestone(user_id: int, checklist_id: int, evaluation_count: int):
        """Process milestone-based suggestions (every 10 evaluations)"""
        if evaluation_count % 10 != 0:
            return

        suggestion = KillChecklistAnalytics.suggest_reordering(checklist_id)
        if suggestion:
            db.session.add(suggestion)
            db.session.commit()

    @staticmethod
    def apply_suggestion(suggestion_id: int, user_id: int) -> bool:
        """Apply a suggestion and update the checklist"""
        suggestion = KillChecklistSuggestion.query\
            .filter_by(id=suggestion_id, user_id=user_id, status='pending')\
            .first()

        if not suggestion:
            return False

        try:
            if suggestion.suggestion_type == 'reorder_criteria':
                SuggestionEngine._apply_reorder_suggestion(suggestion)
            elif suggestion.suggestion_type == 'add_criterion':
                SuggestionEngine._apply_add_criterion_suggestion(suggestion)
            elif suggestion.suggestion_type == 'remove_criterion':
                SuggestionEngine._apply_remove_criterion_suggestion(suggestion)

            suggestion.status = 'accepted'
            suggestion.responded_at = datetime.now(timezone.utc)
            db.session.commit()
            return True

        except Exception as e:
            db.session.rollback()
            print(f"Error applying suggestion {suggestion_id}: {e}")
            return False

    @staticmethod
    def _apply_reorder_suggestion(suggestion: KillChecklistSuggestion):
        """Apply reordering suggestion"""
        optimal_order = suggestion.suggestion_data['optimal_order']

        for item in optimal_order:
            criterion = KillCriterion.query.get(item['id'])
            if criterion:
                criterion.order = item['new_position']

    @staticmethod
    def _apply_add_criterion_suggestion(suggestion: KillChecklistSuggestion):
        """Apply add criterion suggestion"""
        new_criterion_data = suggestion.suggestion_data['new_criterion']

        # Shift existing criteria down
        existing_criteria = KillCriterion.query\
            .filter_by(kill_checklist_id=suggestion.kill_checklist_id)\
            .filter(KillCriterion.order >= new_criterion_data['suggested_position'])\
            .all()

        for criterion in existing_criteria:
            criterion.order += 1

        # Add new criterion
        new_criterion = KillCriterion(
            kill_checklist_id=suggestion.kill_checklist_id,
            question=new_criterion_data['question'],
            order=new_criterion_data['suggested_position'],
            auto_suggested=True,
            source_mistake_id=suggestion.source_data.get('mistake_id')
        )

        db.session.add(new_criterion)

    @staticmethod
    def _apply_remove_criterion_suggestion(suggestion: KillChecklistSuggestion):
        """Apply remove criterion suggestion"""
        criterion_id = suggestion.suggestion_data['criterion_id']
        criterion = KillCriterion.query.get(criterion_id)

        if criterion:
            # Shift remaining criteria up
            remaining_criteria = KillCriterion.query\
                .filter_by(kill_checklist_id=suggestion.kill_checklist_id)\
                .filter(KillCriterion.order > criterion.order)\
                .all()

            for remaining in remaining_criteria:
                remaining.order -= 1

            db.session.delete(criterion)
