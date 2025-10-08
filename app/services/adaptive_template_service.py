"""
Adaptive Template Service

This service makes research templates intelligent and personalized by:
1. Dynamically injecting sector-specific questions based on the company being researched
2. Providing personalized time estimates based on user's historical performance
3. Suggesting process improvements based on usage patterns
"""

from typing import Dict, List, Optional, Any, Tuple
import json
from datetime import datetime, timedelta
from app import db
from app.models import (
    ResearchTemplate, ResearchProject, WorkSession, QuestionBankItem,
    Company, User
)
from collections import defaultdict, Counter
import logging
import statistics

logger = logging.getLogger(__name__)

class AdaptiveTemplateService:
    """Service for making research templates adaptive and personalized"""

    def __init__(self):
        pass

    def get_sector_questions(self, sector: str, user_id: int) -> List[Dict[str, Any]]:
        """
        Get sector-specific questions from the user's question bank

        Args:
            sector: Company sector (e.g., "Banking", "Technology", "Healthcare")
            user_id: User ID

        Returns:
            List of question objects with text, llm_prompt, and metadata
        """
        try:
            # Get questions that match the sector (case-insensitive)
            sector_questions = QuestionBankItem.query.filter(
                QuestionBankItem.user_id == user_id,
                QuestionBankItem.sector.ilike(f'%{sector}%')
            ).all()

            # Also get general questions (no sector) as fallback
            general_questions = QuestionBankItem.query.filter(
                QuestionBankItem.user_id == user_id,
                QuestionBankItem.sector.is_(None)
            ).limit(3).all()

            questions = []

            # Format sector-specific questions
            for q in sector_questions:
                questions.append({
                    'id': q.id,
                    'text': q.text,
                    'llm_prompt': q.llm_prompt,
                    'sector_tag': q.sector,
                    'question_type': 'sector_specific',
                    'relevance_score': 1.0
                })

            # Add general questions if we don't have many sector-specific ones
            if len(questions) < 3:
                for q in general_questions:
                    if q.id not in [existing['id'] for existing in questions]:
                        questions.append({
                            'id': q.id,
                            'text': q.text,
                            'llm_prompt': q.llm_prompt,
                            'sector_tag': q.sector,
                            'question_type': 'general',
                            'relevance_score': 0.7
                        })

            logger.info(f"Found {len(questions)} questions for sector '{sector}' for user {user_id}")
            return questions

        except Exception as e:
            logger.error(f"Error getting sector questions: {e}")
            return []

    def suggest_step_injection(self, template: ResearchTemplate, company: Company,
                             user_id: int) -> Dict[str, Any]:
        """
        Analyze template and suggest step injections based on company sector

        Args:
            template: Research template to enhance
            company: Company being researched
            user_id: User ID

        Returns:
            Dictionary with injection suggestions
        """
        try:
            if not company.sector:
                return {
                    'suggestions': [],
                    'reason': 'Company sector not specified'
                }

            # Get sector-specific questions
            sector_questions = self.get_sector_questions(company.sector, user_id)

            if not sector_questions:
                return {
                    'suggestions': [],
                    'reason': f'No sector-specific questions found for {company.sector}'
                }

            # Analyze template workflow steps to find injection opportunities
            workflow_steps = template.workflow_steps or []

            if not workflow_steps:
                logger.warning(f"Template {template.id} has no workflow steps")
                return {
                    'suggestions': [],
                    'reason': 'Template has no workflow steps defined'
                }

            suggestions = []

            # Find steps that could benefit from sector questions
            for step_idx, step in enumerate(workflow_steps):
                step_name = step.get('name', '').lower()
                step_type = step.get('type', '').lower()

                # Look for financial, competitive, or analysis steps
                injection_opportunities = [
                    ('financial', ['financial', 'revenue', 'profit', 'balance sheet']),
                    ('competitive', ['competitive', 'competition', 'market']),
                    ('management', ['management', 'leadership', 'governance']),
                    ('risk', ['risk', 'threats', 'challenges']),
                    ('valuation', ['valuation', 'pricing', 'value'])
                ]

                for category, keywords in injection_opportunities:
                    if any(keyword in step_name for keyword in keywords):
                        # Find relevant questions for this category
                        relevant_questions = [
                            q for q in sector_questions
                            if any(keyword in q['text'].lower() for keyword in keywords)
                        ]

                        if relevant_questions:
                            suggestions.append({
                                'step_index': step_idx,
                                'step_name': step.get('name'),
                                'category': category,
                                'questions': relevant_questions[:3],  # Limit to 3 questions
                                'injection_point': 'after_step',  # Could be 'before_step', 'after_step', 'replace_step'
                                'confidence': len(relevant_questions) / len(sector_questions)
                            })

            # If no specific matches, suggest adding a new sector-focused step
            if not suggestions and sector_questions:
                suggestions.append({
                    'step_index': len(workflow_steps),  # Add at end
                    'step_name': f'{company.sector} Sector Analysis',
                    'category': 'sector_specific',
                    'questions': sector_questions[:5],
                    'injection_point': 'new_step',
                    'confidence': 0.8
                })

            return {
                'suggestions': suggestions,
                'total_available_questions': len(sector_questions),
                'company_sector': company.sector,
                'template_steps_count': len(workflow_steps)
            }

        except Exception as e:
            logger.error(f"Error suggesting step injection: {e}")
            return {
                'suggestions': [],
                'error': str(e)
            }

    def get_personalized_time_estimates(self, template: ResearchTemplate,
                                      user_id: int) -> Dict[str, Any]:
        """
        Get personalized time estimates based on user's historical performance

        Args:
            template: Research template
            user_id: User ID

        Returns:
            Dictionary with time estimates and insights
        """
        try:
            # Get all work sessions for this user using this template
            work_sessions = WorkSession.query.join(ResearchProject).filter(
                ResearchProject.template_id == template.id,
                WorkSession.user_id == user_id,
                WorkSession.duration_minutes.isnot(None)
            ).all()

            if not work_sessions:
                return {
                    'estimates': [],
                    'insights': [],
                    'reason': 'No historical data available for personalization'
                }

            # Group sessions by step
            step_performance = defaultdict(list)
            for session in work_sessions:
                if session.step_name and session.duration_minutes:
                    step_performance[session.step_name].append(session.duration_minutes)

            # Calculate statistics for each step
            step_estimates = []
            workflow_steps = template.workflow_steps or []

            for step_idx, step in enumerate(workflow_steps):
                step_name = step.get('name')
                if not step_name:
                    continue

                # Get historical durations for this step
                durations = step_performance.get(step_name, [])

                if durations:
                    avg_duration = statistics.mean(durations)
                    median_duration = statistics.median(durations)
                    std_dev = statistics.stdev(durations) if len(durations) > 1 else 0

                    # Provide conservative estimate (75th percentile)
                    sorted_durations = sorted(durations)
                    percentile_75 = sorted_durations[int(0.75 * len(sorted_durations))]

                    step_estimates.append({
                        'step_index': step_idx,
                        'step_name': step_name,
                        'estimated_minutes': int(percentile_75),
                        'average_minutes': int(avg_duration),
                        'median_minutes': int(median_duration),
                        'sessions_count': len(durations),
                        'variability': 'high' if std_dev > avg_duration * 0.5 else 'low',
                        'confidence': min(len(durations) / 5.0, 1.0)  # More sessions = higher confidence
                    })
                else:
                    # No historical data for this step - use template default or reasonable estimate
                    default_estimate = step.get('estimated_minutes', 60)
                    step_estimates.append({
                        'step_index': step_idx,
                        'step_name': step_name,
                        'estimated_minutes': default_estimate,
                        'average_minutes': default_estimate,
                        'median_minutes': default_estimate,
                        'sessions_count': 0,
                        'variability': 'unknown',
                        'confidence': 0.0
                    })

            # Generate insights
            insights = self._generate_time_insights(step_estimates, step_performance)

            return {
                'estimates': step_estimates,
                'insights': insights,
                'total_estimated_minutes': sum(est['estimated_minutes'] for est in step_estimates),
                'historical_sessions': len(work_sessions)
            }

        except Exception as e:
            logger.error(f"Error getting personalized time estimates: {e}")
            return {
                'estimates': [],
                'insights': [],
                'error': str(e)
            }

    def _generate_time_insights(self, step_estimates: List[Dict],
                               step_performance: Dict[str, List[int]]) -> List[str]:
        """Generate insights about user's time management patterns"""
        insights = []

        try:
            # Find steps that consistently take longer than expected
            long_steps = [
                est for est in step_estimates
                if est['sessions_count'] > 2 and est['variability'] == 'high'
            ]

            if long_steps:
                insights.append(
                    f"You tend to spend variable amounts of time on {', '.join(s['step_name'] for s in long_steps[:2])}. "
                    "Consider breaking these into smaller sub-tasks."
                )

            # Find fastest steps
            fast_steps = [
                est for est in step_estimates
                if est['sessions_count'] > 2 and est['average_minutes'] < 30
            ]

            if fast_steps:
                insights.append(
                    f"You're efficient at {', '.join(s['step_name'] for s in fast_steps[:2])}. "
                    "Consider whether these steps need more thorough analysis."
                )

            # Find steps with high confidence (lots of data)
            experienced_steps = [
                est for est in step_estimates
                if est['confidence'] > 0.8
            ]

            if experienced_steps:
                insights.append(
                    f"You have consistent patterns for {len(experienced_steps)} steps. "
                    "Time estimates are highly reliable."
                )

            # Total project insights
            total_sessions = sum(len(durations) for durations in step_performance.values())
            if total_sessions > 10:
                insights.append(
                    f"Based on {total_sessions} previous sessions, this template is well-calibrated to your work style."
                )

        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            insights.append("Unable to generate detailed insights due to insufficient data.")

        return insights

    def inject_questions_into_template(self, template: ResearchTemplate,
                                     suggestions: List[Dict],
                                     selected_suggestion_indices: List[int]) -> Dict[str, Any]:
        """
        Actually inject selected questions into the template workflow

        Args:
            template: Template to modify
            suggestions: List of injection suggestions
            selected_suggestion_indices: Which suggestions to apply

        Returns:
            Modified template workflow and summary of changes
        """
        try:
            workflow_steps = template.workflow_steps.copy() if template.workflow_steps else []
            changes = []

            # Sort suggestions by step_index in reverse order to avoid index shifting
            selected_suggestions = [suggestions[i] for i in selected_suggestion_indices]
            selected_suggestions.sort(key=lambda x: x['step_index'], reverse=True)

            for suggestion in selected_suggestions:
                step_index = suggestion['step_index']
                injection_point = suggestion['injection_point']
                questions = suggestion['questions']

                if injection_point == 'new_step':
                    # Add a new step
                    new_step = {
                        'name': suggestion['step_name'],
                        'type': 'analysis',
                        'description': f"Sector-specific questions for {suggestion.get('category', 'analysis')}",
                        'questions': [
                            {
                                'text': q['text'],
                                'llm_prompt': q['llm_prompt'],
                                'source': 'question_bank',
                                'question_id': q['id']
                            }
                            for q in questions
                        ],
                        'estimated_minutes': len(questions) * 15,  # 15 minutes per question
                        'injected': True,
                        'injection_source': 'adaptive_template'
                    }

                    workflow_steps.append(new_step)
                    changes.append(f"Added new step: '{suggestion['step_name']}' with {len(questions)} questions")

                elif injection_point == 'after_step' and step_index < len(workflow_steps):
                    # Inject questions into existing step
                    target_step = workflow_steps[step_index]

                    if 'questions' not in target_step:
                        target_step['questions'] = []

                    # Add the new questions
                    for q in questions:
                        target_step['questions'].append({
                            'text': q['text'],
                            'llm_prompt': q['llm_prompt'],
                            'source': 'question_bank',
                            'question_id': q['id'],
                            'injected': True
                        })

                    # Update estimated time
                    additional_time = len(questions) * 15
                    current_time = target_step.get('estimated_minutes', 60)
                    target_step['estimated_minutes'] = current_time + additional_time

                    changes.append(f"Added {len(questions)} questions to '{target_step['name']}'")

            return {
                'success': True,
                'modified_workflow': workflow_steps,
                'changes': changes,
                'questions_added': sum(len(s['questions']) for s in selected_suggestions)
            }

        except Exception as e:
            logger.error(f"Error injecting questions into template: {e}")
            return {
                'success': False,
                'error': str(e),
                'changes': []
            }


# Global service instance
adaptive_template_service = AdaptiveTemplateService()


# Convenience functions for easy import
def suggest_template_adaptations(template: ResearchTemplate, company: Company,
                               user_id: int) -> Dict[str, Any]:
    """Get comprehensive template adaptation suggestions"""
    step_suggestions = adaptive_template_service.suggest_step_injection(template, company, user_id)
    time_estimates = adaptive_template_service.get_personalized_time_estimates(template, user_id)

    return {
        'step_injections': step_suggestions,
        'time_estimates': time_estimates,
        'company': {
            'name': company.name,
            'sector': company.sector,
            'ticker': company.ticker_symbol
        },
        'template': {
            'name': template.name,
            'steps_count': len(template.workflow_steps or [])
        }
    }


def apply_template_adaptations(template: ResearchTemplate, adaptations: Dict[str, Any]) -> bool:
    """Apply selected adaptations to a template"""
    try:
        if 'step_injections' in adaptations and adaptations['step_injections'].get('apply'):
            suggestions = adaptations['step_injections']['suggestions']
            selected_indices = adaptations['step_injections'].get('selected_indices', [])

            result = adaptive_template_service.inject_questions_into_template(
                template, suggestions, selected_indices
            )

            if result['success']:
                template.workflow_steps = result['modified_workflow']
                db.session.commit()
                return True

        return False

    except Exception as e:
        logger.error(f"Error applying template adaptations: {e}")
        return False