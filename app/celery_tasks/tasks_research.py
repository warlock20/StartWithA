"""
Research & Company Analysis Celery Tasks

Background tasks for competitor analysis, bias check, and argos deep analysis.
"""

import json
import logging

from app import db, create_app
from app.models import Company, BackgroundTask, WorkSession, User, ResearchProject, BiasCheckResult
from celery_app import celery

from app.services.ai import generate_ai_content, ai_service
from app.services.ai.prompt_service import get_competitor_analysis_prompt, prompt_service
from app.services.ai.config import AITaskType
from app.services.argos import ArgosService
from app.services.research_data_service import ResearchDataService
from app.utils.time_utils import now_utc

logger = logging.getLogger(__name__)


@celery.task(bind=True)
def competitor_analysis_task(self, task_id, company_data):
    """
    A Celery task to perform AI competitor analysis for a company.
    """
    app = create_app()
    with app.app_context():
        try:
            # Get fresh task instance from database
            task = BackgroundTask.query.get(task_id)
            if not task:
                logger.error(f"TASK {self.request.id}: Task {task_id} not found")
                return f"Task {task_id} not found"

            # Update task status to running
            task.status = 'running'
            task.started_at = now_utc()
            db.session.commit()

            logger.info(f"TASK {self.request.id}: Starting competitor analysis for {company_data['name']}")

            # Generate the analysis prompt
            analysis_prompt = get_competitor_analysis_prompt(
                'landscape_analysis',
                company_name=company_data['name'],
                ticker_symbol=company_data['ticker_symbol'],
                company_description=company_data['summary'] or 'No description available',
                sector=company_data['sector'] or 'Unknown',
                industry=company_data['industry'] or 'Unknown'
            )

            # Call LLM service - this is where the long wait happens
            logger.info(f"TASK {self.request.id}: Calling LLM service...")
            competitor_analysis = generate_ai_content(analysis_prompt, max_tokens=2000)

            # Store result in work session
            session = WorkSession.query.filter_by(
                project_id=task.project_id,
                user_id=task.user_id,
                step_index=task.step_index,
                end_time=None
            ).first()

            if session:
                session.notes = competitor_analysis
                session.updated_at = now_utc()

            # Update task as completed
            task.status = 'completed'
            task.completed_at = now_utc()
            task.result = json.dumps({
                "analysis": competitor_analysis,
                "message": "Competitor analysis completed successfully!"
            })

            db.session.commit()

            logger.info(f"TASK {self.request.id}: Completed successfully")
            return f"Competitor analysis completed successfully for {company_data['name']}"

        except Exception as e:
            logger.error(f"TASK {self.request.id}: Failed - {e}", exc_info=True)

            # Update task as failed
            task = BackgroundTask.query.get(task_id)
            if task:
                task.status = 'failed'
                task.completed_at = now_utc()
                task.error_message = str(e)
                db.session.commit()

            return f"Task failed: {e}"


# Constants for bias check
BIAS_CHECK_PROMPT_CATEGORY = "research"
BIAS_CHECK_PROMPT_NAME = "bias_check"


@celery.task(bind=True)
def bias_check_task(self, task_id, user_id, project_id):
    """
    Celery background task for cognitive bias analysis.

    Args:
        task_id: BackgroundTask ID for status tracking
        user_id: User ID for token tracking
        project_id: ResearchProject ID to analyze
    """
    app = create_app()
    with app.app_context():
        task = BackgroundTask.query.get(task_id)
        if not task:
            logger.error(f"TASK {self.request.id}: Task {task_id} not found")
            return {"status": "failed", "message": "Task not found"}

        try:
            # 1. UPDATE STATUS TO RUNNING
            task.status = 'running'
            task.started_at = now_utc()
            db.session.commit()

            # 2. GET PROJECT AND DATA
            project = ResearchProject.query.get(project_id)
            if not project:
                raise ValueError(f"Project {project_id} not found")

            thesis_text = ResearchDataService.get_all_text(project, include_metadata=True)
            word_count = len(thesis_text.split())

            if word_count < 200:
                raise ValueError(f"Insufficient research text. Found {word_count} words, minimum is 200.")

            company_name = project.company.name if project.company else project.project_name
            sector = project.company.sector.display_name if project.company and project.company.sector else None

            # 3. LOAD PROMPT AND CALL AI
            prompt_data = prompt_service.get_prompt_with_metadata(
                category=BIAS_CHECK_PROMPT_CATEGORY,
                name=BIAS_CHECK_PROMPT_NAME,
                company_name=company_name,
                sector=sector,
                thesis_text=thesis_text,
            )

            prompt_text = prompt_data['prompt']
            metadata = prompt_data.get('metadata', {})
            system_context = prompt_data.get('system_context')

            logger.info(f"TASK {self.request.id}: Running bias check for project {project_id} (words: {word_count})")

            result = ai_service.generate_json(
                prompt=prompt_text,
                max_tokens=metadata.get('max_tokens', 3000),
                temperature=metadata.get('temperature', 0.4),
                task=AITaskType.BIAS_CHECK,
                system=system_context,  # Pass system context for Gemini
            )

            if not result:
                raise ValueError("AI analysis returned no result")

            # 4. ESTIMATE TOKENS AND TRACK USAGE
            tokens_estimate = len(prompt_text) // 4 + len(str(result)) // 4

            user = User.query.get(user_id)
            if user:
                user.increment_ai_tokens(tokens_estimate)

            # 5. SAVE BIAS CHECK RESULT
            bias_result = BiasCheckResult(
                user_id=user_id,
                project_id=project_id,
                overall_score=result.get('overall_score', 50),
                overall_level=result.get('overall_level', 'moderate'),
                excitement_score=result.get('excitement_score', 50),
                balance_assessment=result.get('balance_assessment'),
                biases_detected=result.get('biases', []),
                strengths=result.get('strengths', []),
                word_count=result.get('meta', {}).get('word_count', word_count),
                bullish_points=result.get('meta', {}).get('bullish_points'),
                bearish_points=result.get('meta', {}).get('bearish_points'),
                risks_acknowledged=result.get('meta', {}).get('risks_acknowledged'),
                certainty_phrases=result.get('meta', {}).get('certainty_phrases'),
                superlatives=result.get('meta', {}).get('superlatives'),
                tokens_used=tokens_estimate,
                model_used='gemini',
                prompt_version=metadata.get('version', '1.0')
            )
            db.session.add(bias_result)
            db.session.flush()  # Flush to get bias_result.id before storing in task

            # 6. UPDATE TASK AS COMPLETED
            task.status = 'completed'
            task.completed_at = now_utc()
            task.result = json.dumps({
                'result_id': bias_result.id,
                'overall_score': bias_result.overall_score,
                'tokens_used': tokens_estimate
            })
            db.session.commit()

            logger.info(f"TASK {self.request.id}: Bias check completed, score={bias_result.overall_score}")
            return {"status": "success", "result_id": bias_result.id, "tokens_used": tokens_estimate}

        except Exception as e:
            logger.error(f"TASK {self.request.id}: Bias check failed - {e}", exc_info=True)

            # Update task as failed
            task = BackgroundTask.query.get(task_id)
            if task:
                task.status = 'failed'
                task.completed_at = now_utc()
                task.error_message = str(e)
                db.session.commit()

            return {"status": "failed", "message": str(e)}


# =========================================================================
# Counter-Evidence Generation (Companion)
# =========================================================================

@celery.task(bind=True)
def counter_evidence_task(self, task_id, user_id, project_id, finding_text, research_question, step_index):
    """
    Generate counter-evidence for a research finding asynchronously.

    Args:
        task_id: BackgroundTask ID for status tracking
        user_id: User ID
        project_id: ResearchProject ID
        finding_text: The finding to challenge
        research_question: The research question context
        step_index: Current step index
    """
    app = create_app()
    with app.app_context():
        task = BackgroundTask.query.get(task_id)
        if not task:
            logger.error(f"TASK {self.request.id}: Task {task_id} not found")
            return {"status": "failed", "message": "Task not found"}

        try:
            task.status = 'running'
            task.started_at = now_utc()
            db.session.commit()

            argos = ArgosService(user_id=user_id)
            context = argos.build_research_context(project_id, step_index=step_index)
            result = argos.generate_counter_evidence(context, finding_text, research_question)

            user = User.query.get(user_id)
            if user:
                user.increment_ai_tokens(500)

            task.status = 'completed'
            task.completed_at = now_utc()
            task.result = json.dumps({'counter_evidence': result})
            db.session.commit()

            logger.info(f"TASK {self.request.id}: Counter-evidence generated for project {project_id}")
            return {"status": "completed", "counter_evidence": result}

        except Exception as e:
            logger.error(f"TASK {self.request.id}: Counter-evidence failed - {e}", exc_info=True)

            task = BackgroundTask.query.get(task_id)
            if task:
                task.status = 'failed'
                task.completed_at = now_utc()
                task.error_message = str(e)
                db.session.commit()

            return {"status": "failed", "message": str(e)}


# =========================================================================
# Argos Deep Analysis (Background)
# =========================================================================

@celery.task(bind=True)
def argos_deep_analysis_task(self, task_id, user_id, company_id, step_type, step_context, current_text, include_companion_warnings):
    """
    Run Argos deep analysis asynchronously.

    Args:
        task_id: BackgroundTask ID for status tracking
        user_id: User ID
        company_id: Company ID to analyze
        step_type: Research step type (checklist, free_research, thesis, completion)
        step_context: Optional context dict for the step
        current_text: Current research text for semantic matching
        include_companion_warnings: Whether to prepend companion warnings to current_text
    """
    app = create_app()
    with app.app_context():
        task = BackgroundTask.query.get(task_id)
        if not task:
            logger.error(f"TASK {self.request.id}: Task {task_id} not found")
            return {"status": "failed", "message": "Task not found"}

        try:
            task.status = 'running'
            task.started_at = now_utc()
            db.session.commit()

            argos = ArgosService(user_id=user_id)

            # Optionally prepend companion warnings to current_text
            if include_companion_warnings and current_text:
                warnings = argos.get_warnings_by_company(company_id)
                if warnings:
                    warning_summary = "\n".join(
                        f"- [{w.get('type', 'warning')}] {w.get('message', '')}" for w in warnings
                    )
                    current_text = f"[Companion Warnings]\n{warning_summary}\n\n{current_text}"

            result = argos.check(
                company_id=company_id,
                step_type=step_type,
                step_context=step_context or {},
                current_text=current_text,
            )

            user = User.query.get(user_id)
            if user:
                user.increment_ai_tokens(500)

            task.status = 'completed'
            task.completed_at = now_utc()
            task.result = json.dumps(result.to_dict())
            db.session.commit()

            logger.info(f"TASK {self.request.id}: Argos deep analysis completed for company {company_id}")
            return {"status": "completed", "result": result.to_dict()}

        except Exception as e:
            logger.error(f"TASK {self.request.id}: Argos deep analysis failed - {e}", exc_info=True)

            task = BackgroundTask.query.get(task_id)
            if task:
                task.status = 'failed'
                task.completed_at = now_utc()
                task.error_message = str(e)
                db.session.commit()

            return {"status": "failed", "message": str(e)}
