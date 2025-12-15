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
    QualitativeAnalysis
)

logger = logging.getLogger(__name__)


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
        if not project or not project.template or not project.template.workflow_steps:
            return 0.0

        if step_index < 0 or step_index >= len(project.template.workflow_steps):
            return 0.0

        if step_index in (project.completed_steps or []):
            return 100.0

        step = project.template.workflow_steps[step_index]
        step_type = step.get('type', '')

        calculator = STEP_CALCULATORS.get(step_type)
        if calculator:
            return calculator(project, step, step_index)

        return 0.0


def calculate_checklist_progress(project, step, step_index):
    """
    Calculate progress for a checklist step.

    Progress is based on how many checklist items have been answered
    out of the total items in the checklist.
    """
    try:
        config = step.get('config', {})
        checklist_id = config.get('checklist_id')
        if not checklist_id:
            return 0.0

        # Convert to int if it's a string
        checklist_id = int(checklist_id)

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

        checklist = Checklist.query.get(checklist_id)
        if not checklist:
            return 0.0

        total_items = checklist.items.count()
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


def calculate_porters_progress(project, step, step_index):
    """
    Calculate progress for a Porter's Five Forces analysis step.

    Progress is based on whether the analysis exists and how many
    of the 5 forces have been analyzed.
    """
    try:
        porters = QualitativeAnalysis.query.filter_by(
            company_id=project.company_id,
            user_id=project.user_id,
            model_type='Porter'
        ).first()

        if not porters or not porters.content:
            return 0.0

        content = porters.content
        filled_forces = 0
        if content.get('competitive_rivalry'):
            filled_forces += 1
        if content.get('supplier_power'):
            filled_forces += 1
        if content.get('buyer_power'):
            filled_forces += 1
        if content.get('threat_of_substitution'):
            filled_forces += 1
        if content.get('threat_of_new_entry'):
            filled_forces += 1

        progress = (filled_forces / 5) * 100
        return round(progress, 1)

    except Exception as e:
        logger.error(f"Error calculating Porter's progress for project {project.id}, step {step_index}: {e}")
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


STEP_CALCULATORS = {
    'checklist': calculate_checklist_progress,
    'kill_checklist': calculate_kill_checklist_progress,
    'kill_checklist_reference': calculate_kill_checklist_progress,
    'swot': calculate_swot_progress,
    'porters': calculate_porters_progress,
    'porter_five_forces': calculate_porters_progress,
    'custom': calculate_custom_step_progress,
}
