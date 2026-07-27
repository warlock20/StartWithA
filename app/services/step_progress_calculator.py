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
Step Progress Calculator Service

This service calculates progress for individual research workflow steps.
Each step type (checklist, kill_checklist, SWOT, etc.) has its own progress calculator.
"""

import logging

from app.models import (
    ChecklistAnalysis,
    ChecklistAnswer,
    KillSession,
    KillAnswer,
    Checklist,
    KillChecklist,
    IdeaPipeline,
    QualitativeAnalysis,
    FreeResearchQuestion,
)
from app.utils.checklist_utils import get_all_ordered_items_for_checklist

logger = logging.getLogger(__name__)


def _resolve_checklist_id(project, step, step_index):
    """Resolve the effective checklist_id, respecting step_overrides."""
    if project.step_overrides and str(step_index) in project.step_overrides:
        override_id = project.step_overrides[str(step_index)].get('checklist_id')
        if override_id:
            return int(override_id)

    config = step.get('config', {})
    checklist_id = config.get('checklist_id')
    if checklist_id:
        return int(checklist_id)
    return None


class StepProgressCalculator:
    """
    Calculate progress for individual research workflow steps.
    Delegates to specific calculators based on step type.
    """

    @staticmethod
    def get_step_progress(project, step_index):
        """
        Calculate progress for a specific step in a research project.

        Args:
            project: ResearchProject instance
            step_index: Index of the step in the workflow

        Returns:
            float: Progress percentage (0-100)
        """
        if not project or not project.workflow_steps:
            return 0.0

        if step_index < 0 or step_index >= project.step_count:
            return 0.0

        if step_index in (project.completed_steps or []):
            return 100.0

        step = project.workflow_steps[step_index]
        step_type = step.get('type', '')

        calculator = STEP_CALCULATORS.get(step_type)
        if calculator:
            return calculator(project, step, step_index)

        return 0.0


def calculate_checklist_progress(project, step, step_index):
    """
    Calculate progress for a checklist step.

    Progress is based on how many checklist items have been answered
    out of the total navigable items in the checklist.
    """
    try:
        checklist_id = _resolve_checklist_id(project, step, step_index)
        if not checklist_id:
            return 0.0

        analysis = ChecklistAnalysis.query.filter_by(
            company_id=project.company_id,
            checklist_id=checklist_id,
            user_id=project.user_id
        ).order_by(ChecklistAnalysis.start_date.desc()).first()

        if not analysis:
            return 0.0

        if analysis.status == 'completed':
            return 100.0

        answered_count = ChecklistAnswer.query.filter_by(
            checklist_analysis_id=analysis.id
        ).filter(
            ChecklistAnswer.answer_text.isnot(None),
            ChecklistAnswer.answer_text != ''
        ).count()

        total_items = len(get_all_ordered_items_for_checklist(checklist_id))
        if total_items == 0:
            return 0.0

        progress = (answered_count / total_items) * 100
        return round(progress, 1)

    except Exception as e:
        logger.error(f"Error calculating checklist progress for project {project.id}, step {step_index}: {e}")
        return 0.0


def calculate_kill_checklist_progress(project, step, step_index):
    """
    Calculate progress for a kill checklist step.

    Progress is based on how many kill criteria have been evaluated.
    """
    try:
        config = step.get('config', {})
        kill_checklist_id = config.get('kill_checklist_id')
        if not kill_checklist_id:
            return 0.0

        # Convert to int if it's a string
        kill_checklist_id = int(kill_checklist_id)

        idea = IdeaPipeline.query.filter_by(
            company_id=project.company_id,
            user_id=project.user_id
        ).first()

        if not idea:
            return 0.0

        session = KillSession.query.filter_by(
            idea_id=idea.id,
            kill_checklist_id=kill_checklist_id
        ).order_by(KillSession.created_at.desc()).first()

        if not session:
            return 0.0

        if session.status == 'completed':
            return 100.0

        answered_count = KillAnswer.query.filter_by(
            kill_session_id=session.id
        ).filter(
            KillAnswer.answer.isnot(None),
            KillAnswer.answer != ''
        ).count()

        kill_checklist = KillChecklist.query.get(kill_checklist_id)
        if not kill_checklist:
            return 0.0

        total_criteria = len(kill_checklist.criteria or [])
        if total_criteria == 0:
            return 0.0

        progress = (answered_count / total_criteria) * 100
        return round(progress, 1)

    except Exception as e:
        logger.error(f"Error calculating kill checklist progress for project {project.id}, step {step_index}: {e}")
        return 0.0


def calculate_model_progress(project, step, step_index):
    """
    Calculate progress for a model step (e.g. SWOT Analysis).

    Delegates to the appropriate model calculator based on model_type.
    """
    config = step.get('config', {})
    model_type = config.get('model_type', '')

    if model_type == 'SWOT Analysis':
        return calculate_swot_progress(project, step, step_index)

    return 0.0


def calculate_swot_progress(project, step, step_index):
    """
    Calculate progress for a SWOT analysis step.

    Progress is based on whether the SWOT analysis has been created and
    how complete it is (all 4 quadrants filled).
    """
    try:
        swot = QualitativeAnalysis.query.filter_by(
            company_id=project.company_id,
            user_id=project.user_id,
            model_type='SWOT'
        ).first()

        if not swot or not swot.content:
            return 0.0

        content = swot.content
        filled_quadrants = 0
        if content.get('strengths'):
            filled_quadrants += 1
        if content.get('weaknesses'):
            filled_quadrants += 1
        if content.get('opportunities'):
            filled_quadrants += 1
        if content.get('threats'):
            filled_quadrants += 1

        progress = (filled_quadrants / 4) * 100
        return round(progress, 1)

    except Exception as e:
        logger.error(f"Error calculating SWOT progress for project {project.id}, step {step_index}: {e}")
        return 0.0


def calculate_custom_step_progress(project, step, step_index):
    """
    Calculate progress for a custom step.

    For custom steps, we check if there are notes or results stored
    in the project's step_results.
    """
    try:
        if project.step_results:
            step_result = project.step_results.get(str(step_index))
            if step_result:
                return 100.0

        if project.step_notes:
            step_note = project.step_notes.get(str(step_index))
            if step_note:
                return 100.0

        return 0.0

    except Exception as e:
        logger.error(f"Error calculating custom step progress for project {project.id}, step {step_index}: {e}")
        return 0.0


def calculate_free_research_progress(project, step, step_index):
    """
    Calculate progress for a free research step.

    Progress is based on the ratio of answered questions to total questions.
    If no questions exist yet, progress is 0%.
    """
    try:
        questions = FreeResearchQuestion.query.filter_by(
            project_id=project.id,
            step_index=step_index
        ).all()

        if not questions:
            return 0.0

        answered_count = sum(1 for q in questions if q.status == 'answered')
        total_count = len(questions)

        progress = (answered_count / total_count) * 100
        return round(progress, 1)

    except Exception as e:
        logger.error(f"Error calculating free research progress for project {project.id}, step {step_index}: {e}")
        return 0.0


def calculate_thesis_progress(project, step, step_index):
    """
    Calculate progress for a thesis writing step.

    Binary: 100% if investment_thesis has content, 0% otherwise.
    """
    try:
        if project.investment_thesis:
            return 100.0
        return 0.0
    except Exception as e:
        logger.error(f"Error calculating thesis progress for project {project.id}, step {step_index}: {e}")
        return 0.0


STEP_CALCULATORS = {
    'checklist': calculate_checklist_progress,
    'kill_checklist': calculate_kill_checklist_progress,
    'kill_checklist_reference': calculate_kill_checklist_progress,
    'model': calculate_model_progress,
    'swot': calculate_swot_progress,
    'free_research': calculate_free_research_progress,
    'competitor_analysis': calculate_custom_step_progress,
    'thesis_writing': calculate_thesis_progress,
    'custom': calculate_custom_step_progress,
}
