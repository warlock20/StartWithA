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
from sqlalchemy import func, desc
from app import db
from app.models import (KillChecklist, KillCriterion, KillSession, KillAnswer,
                       KillChecklistSuggestion, MistakeLog, IdeaPipeline)
from app.services.ai import generate_text
from app.services.ai import get_kill_checklist_prompt
import re
from typing import List, Dict, Optional, Tuple


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

    @staticmethod
    def analyze_mistake_for_criteria(mistake_id: int) -> Optional[KillChecklistSuggestion]:
        """
        Analyze a mistake log entry and suggest new kill criteria using LLM intelligence.
        This enhanced version uses LLM to understand context and generate more accurate criteria.
        """
        return KillChecklistAnalytics._analyze_mistake_with_llm(mistake_id)

    @staticmethod
    def _analyze_mistake_with_llm(mistake_id: int) -> Optional[KillChecklistSuggestion]:
        """LLM-powered mistake analysis for more intelligent criterion extraction"""
        mistake = MistakeLog.query.get(mistake_id)
        if not mistake:
            return None

        # Get user's default kill checklist
        checklist = KillChecklist.query.filter_by(
            user_id=mistake.user_id,
            is_default=True
        ).first()

        if not checklist:
            return None

        # Get existing criteria for context
        existing_criteria = [c.question for c in checklist.criteria.all()]
        existing_context = "\n".join([f"- {criteria}" for criteria in existing_criteria[:5]]) if existing_criteria else "No existing criteria"

        # Use centralized prompt management
        llm_prompt = get_kill_checklist_prompt(
            'mistake_analysis',
            mistake_title=mistake.title,
            mistake_description=mistake.description,
            mistake_type=mistake.mistake_type,
            mistake_severity=mistake.severity,
            mistake_cost=f"${mistake.cost_estimate:.2f}" if mistake.cost_estimate else "Unknown",
            mistake_date=mistake.occurred_date.strftime('%Y-%m-%d') if mistake.occurred_date else "Unknown",
            existing_criteria=existing_context
        )

        try:
            # Generate LLM response
            llm_response = generate_text(llm_prompt, max_tokens=800)

            if not llm_response:
                # Fallback to rule-based extraction
                return KillChecklistAnalytics._analyze_mistake_with_rules(mistake_id)

            # Parse LLM response
            import json
            try:
                criteria_data = json.loads(llm_response)
            except json.JSONDecodeError:
                # Try to extract criteria from unstructured response
                criteria_data = KillChecklistAnalytics._parse_unstructured_llm_response(llm_response)

            if not criteria_data.get('suggested_criteria'):
                return None

            # Take the best criterion suggestion
            best_criterion = max(criteria_data['suggested_criteria'],
                               key=lambda x: x.get('confidence', 0.5))

            # Check if similar criterion already exists
            if KillChecklistAnalytics._criterion_already_exists(checklist.id, best_criterion['question']):
                return None

            # Calculate confidence based on mistake severity and LLM confidence
            base_confidence = best_criterion.get('confidence', 0.7)
            severity_boost = min(mistake.severity / 10.0, 0.3)  # Up to 30% boost for severity
            cost_boost = min((mistake.cost_estimate or 0) / 50000.0, 0.2) if mistake.cost_estimate else 0  # Up to 20% boost for high costs

            final_confidence = min(base_confidence + severity_boost + cost_boost, 0.95)

            suggestion_data = {
                "new_criterion": {
                    "question": best_criterion['question'],
                    "suggested_position": 1,  # High priority for mistake-based criteria
                    "source": "llm_mistake_analysis",
                    "mistake_cost": mistake.cost_estimate,
                    "mistake_severity": mistake.severity,
                    "reasoning": best_criterion.get('reasoning', ''),
                    "threshold_type": best_criterion.get('threshold_type', 'qualitative')
                },
                "related_mistakes": [mistake_id],
                "llm_analysis": criteria_data.get('analysis', ''),
                "alternative_criteria": criteria_data['suggested_criteria'][1:] if len(criteria_data['suggested_criteria']) > 1 else []
            }

            suggestion = KillChecklistSuggestion(
                user_id=mistake.user_id,
                kill_checklist_id=checklist.id,
                suggestion_type='add_criterion',
                title=f"Add criterion to prevent {mistake.mistake_type.replace('_', ' ').title()} mistakes",
                description=f"AI analysis suggests: '{best_criterion['question']}' - This could have prevented your ${mistake.cost_estimate:.0f if mistake.cost_estimate else 'costly'} mistake.",
                reasoning=f"LLM Analysis: {best_criterion.get('reasoning', '')}. {criteria_data.get('analysis', '')}",
                suggestion_data=suggestion_data,
                effectiveness_gain=KillChecklistAnalytics._estimate_criterion_effectiveness(best_criterion, mistake),
                confidence_score=final_confidence,
                trigger_event='mistake_logged_llm',
                source_data={"mistake_id": mistake_id, "cost": mistake.cost_estimate, "llm_used": True}
            )

            return suggestion

        except Exception as e:
            print(f"LLM analysis failed for mistake {mistake_id}: {e}")
            # Fallback to rule-based extraction
            return KillChecklistAnalytics._analyze_mistake_with_rules(mistake_id)

    @staticmethod
    def _analyze_mistake_with_rules(mistake_id: int) -> Optional[KillChecklistSuggestion]:
        """Fallback rule-based mistake analysis (original implementation)"""
        mistake = MistakeLog.query.get(mistake_id)
        if not mistake:
            return None

        # Get user's default kill checklist
        checklist = KillChecklist.query.filter_by(
            user_id=mistake.user_id,
            is_default=True
        ).first()

        if not checklist:
            return None

        # Extract potential criteria from mistake description and lessons learned
        text_to_analyze = f"{mistake.description} {getattr(mistake, 'lesson_learned', '')}"

        suggested_criteria = KillChecklistAnalytics._extract_criteria_from_text(text_to_analyze)

        if not suggested_criteria:
            return None

        # Select the best criterion suggestion
        best_criterion = suggested_criteria[0]  # For now, take the first one

        # Check if a similar criterion already exists
        if KillChecklistAnalytics._criterion_already_exists(checklist.id, best_criterion):
            return None

        suggestion_data = {
            "new_criterion": {
                "question": best_criterion,
                "suggested_position": 1,  # Add at the top for high-cost mistakes
                "source": "rule_based_analysis",
                "mistake_cost": mistake.cost_estimate,
                "mistake_severity": mistake.severity
            },
            "related_mistakes": [mistake_id]
        }

        suggestion = KillChecklistSuggestion(
            user_id=mistake.user_id,
            kill_checklist_id=checklist.id,
            suggestion_type='add_criterion',
            title=f"Add criterion to prevent costly mistakes",
            description=f"Based on your ${mistake.cost_estimate:.0f} mistake, consider adding: '{best_criterion}'",
            reasoning=f"This mistake cost you ${mistake.cost_estimate:.0f}. Adding a kill criterion to catch similar issues early could prevent future losses.",
            suggestion_data=suggestion_data,
            effectiveness_gain=0.1,  # Estimated 10% improvement for mistake-based criteria
            confidence_score=min(mistake.severity / 10.0, 0.9),  # Higher confidence for severe mistakes
            trigger_event='mistake_logged_rules',
            source_data={"mistake_id": mistake_id, "cost": mistake.cost_estimate, "llm_used": False}
        )

        return suggestion

    @staticmethod
    def _parse_unstructured_llm_response(response: str) -> Dict:
        """
        Parse unstructured LLM response to extract criteria suggestions.
        Fallback when LLM doesn't return proper JSON format.
        """
        criteria_suggestions = []

        # Try to extract questions from response
        import re

        # Look for question patterns
        question_patterns = [
            r'"([^"]*\?)"',  # Questions in quotes
            r'Is\s+[^?]*\?',  # Questions starting with "Is"
            r'Does\s+[^?]*\?',  # Questions starting with "Does"
            r'Can\s+[^?]*\?',   # Questions starting with "Can"
        ]

        questions = []
        for pattern in question_patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            questions.extend(matches)

        # Clean and deduplicate questions
        unique_questions = list(set([q.strip() for q in questions if q.strip() and '?' in q]))

        # Convert to standard format
        for question in unique_questions[:2]:  # Take top 2
            criteria_suggestions.append({
                "question": question,
                "reasoning": "Extracted from LLM analysis",
                "threshold_type": "qualitative",
                "confidence": 0.6  # Lower confidence for unstructured parsing
            })

        return {
            "suggested_criteria": criteria_suggestions,
            "analysis": "Criteria extracted from unstructured LLM response"
        }

    @staticmethod
    def _estimate_criterion_effectiveness(criterion: Dict, mistake: 'MistakeLog') -> float:
        """
        Estimate the effectiveness gain from adding a new criterion based on mistake analysis.
        """
        base_effectiveness = 0.1  # 10% base improvement

        # Boost based on mistake severity
        severity_boost = (mistake.severity / 10.0) * 0.05  # Up to 5% boost

        # Boost based on mistake cost
        if mistake.cost_estimate:
            # Higher cost mistakes suggest more impactful criteria
            cost_boost = min(mistake.cost_estimate / 100000.0, 0.05)  # Up to 5% boost for $100k+ mistakes
        else:
            cost_boost = 0

        # Boost based on threshold type (numerical criteria tend to be more effective)
        threshold_boost = 0.02 if criterion.get('threshold_type') == 'numerical' else 0

        # Boost based on LLM confidence
        confidence_boost = (criterion.get('confidence', 0.5) - 0.5) * 0.04  # Up to 2% boost for high confidence

        total_effectiveness = base_effectiveness + severity_boost + cost_boost + threshold_boost + confidence_boost

        # Cap at reasonable maximum
        return min(total_effectiveness, 0.25)  # Max 25% improvement

    @staticmethod
    def generate_periodic_suggestions(user_id: int) -> List[KillChecklistSuggestion]:
        """
        Generate periodic suggestions for all user's checklists based on accumulated data.

        Args:
            user_id: ID of the user

        Returns:
            List of KillChecklistSuggestion objects
        """
        suggestions = []

        # Get all user's kill checklists
        checklists = KillChecklist.query.filter_by(user_id=user_id).all()

        for checklist in checklists:
            # Skip if checklist hasn't been used enough
            if checklist.total_ideas_evaluated < 10:
                continue

            # Check for reordering opportunities
            reorder_suggestion = KillChecklistAnalytics.suggest_reordering(checklist.id)
            if reorder_suggestion:
                suggestions.append(reorder_suggestion)

            # Check for underperforming criteria
            cleanup_suggestions = KillChecklistAnalytics._suggest_cleanup(checklist.id)
            suggestions.extend(cleanup_suggestions)

        return suggestions

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
    def _extract_criteria_from_text(text: str) -> List[str]:
        """
        Extract potential kill criteria from mistake description using NLP patterns.
        This is a simplified version - could be enhanced with ML models.
        """
        criteria_patterns = [
            r"debt.{0,20}ratio.{0,20}(above|over|exceeds?|greater than)\s*([0-9.]+)",
            r"(revenue|sales).{0,20}concentration.{0,20}(above|over|exceeds?)\s*([0-9]+)%",
            r"cash.{0,20}(burn|runway).{0,20}(less than|under|below)\s*([0-9]+)",
            r"(gross|operating|net).{0,20}margin.{0,20}(less than|under|below)\s*([0-9]+)%",
            r"market.{0,20}cap.{0,20}(less than|under|below).{0,20}\$([0-9.]+)",
            r"p/e.{0,20}ratio.{0,20}(above|over|exceeds?)\s*([0-9.]+)",
        ]

        suggested_criteria = []

        for pattern in criteria_patterns:
            matches = re.finditer(pattern, text.lower())
            for match in matches:
                groups = match.groups()
                if len(groups) >= 2:
                    # Convert pattern match to kill criterion question
                    criterion = KillChecklistAnalytics._pattern_to_criterion(pattern, groups)
                    if criterion:
                        suggested_criteria.append(criterion)

        # Add some common criteria based on mistake types
        common_criteria = {
            "balance sheet": "Is debt-to-equity ratio below 0.5?",
            "cash flow": "Does the company have positive free cash flow?",
            "concentration": "Is customer concentration below 30%?",
            "margin": "Are gross margins above 20%?",
            "valuation": "Is P/E ratio reasonable for the sector?",
        }

        for keyword, criterion in common_criteria.items():
            if keyword in text.lower():
                suggested_criteria.append(criterion)

        return list(set(suggested_criteria))  # Remove duplicates

    @staticmethod
    def _pattern_to_criterion(pattern: str, groups: tuple) -> Optional[str]:
        """Convert regex pattern matches to kill criterion questions"""
        # This is a simplified mapper - would be more sophisticated in production
        if "debt" in pattern:
            return f"Is debt-to-equity ratio below {groups[-1]}?"
        elif "concentration" in pattern:
            return f"Is customer concentration below {groups[-1]}%?"
        elif "margin" in pattern:
            return f"Are margins above {groups[-1]}%?"
        elif "cash" in pattern:
            return f"Does company have more than {groups[-1]} months cash runway?"
        elif "market cap" in pattern:
            return f"Is market cap above ${groups[-1]}B?"
        elif "p/e" in pattern:
            return f"Is P/E ratio below {groups[-1]}?"

        return None

    @staticmethod
    def _criterion_already_exists(checklist_id: int, question: str) -> bool:
        """Check if a similar criterion already exists in the checklist"""
        existing = KillCriterion.query.filter_by(kill_checklist_id=checklist_id).all()

        # Simple similarity check - could be enhanced with NLP
        for criterion in existing:
            if KillChecklistAnalytics._questions_similar(criterion.question, question):
                return True

        return False

    @staticmethod
    def _questions_similar(q1: str, q2: str, threshold: float = 0.7) -> bool:
        """Check if two questions are similar (simplified version)"""
        # Convert to lowercase and split into words
        words1 = set(q1.lower().split())
        words2 = set(q2.lower().split())

        # Calculate Jaccard similarity
        intersection = words1.intersection(words2)
        union = words1.union(words2)

        if len(union) == 0:
            return False

        similarity = len(intersection) / len(union)
        return similarity >= threshold

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
    def process_mistake_logged(mistake_id: int):
        """Process suggestions when a new mistake is logged"""
        suggestion = KillChecklistAnalytics.analyze_mistake_for_criteria(mistake_id)
        if suggestion:
            db.session.add(suggestion)
            db.session.commit()

    @staticmethod
    def get_pending_suggestions(user_id: int) -> List[KillChecklistSuggestion]:
        """Get all pending suggestions for a user"""
        return KillChecklistSuggestion.query\
            .filter_by(user_id=user_id, status='pending')\
            .filter(~KillChecklistSuggestion.is_expired)\
            .order_by(desc(KillChecklistSuggestion.effectiveness_gain))\
            .all()

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