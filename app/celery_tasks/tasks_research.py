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
Research & Company Analysis Celery Tasks

Background tasks for bias check, Argos deep analysis and AI research assist.
"""

import json
import logging


from app import db, create_app
from app.models import Company, BackgroundTask, User, ResearchProject, BiasCheckResult, AIResearchFeedback
from celery_app import celery
from celery.exceptions import SoftTimeLimitExceeded
from config import Config

from app.services.ai import ai_service
from app.services.ai.prompt_service import prompt_service, resolve_model_provider
from app.services.ai.config import AITaskType
from app.services.argos import ArgosService
from app.services.ai_research_assistant import ai_research_assistant
from app.services.research_data_service import ResearchDataService
from app.utils.time_utils import now_utc

logger = logging.getLogger(__name__)


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
            model_enum, provider_enum = resolve_model_provider(
                metadata, user_id=user_id, prompt_category=BIAS_CHECK_PROMPT_CATEGORY,
            )

            logger.info(f"TASK {self.request.id}: Running bias check for project {project_id} (words: {word_count})")

            result = ai_service.generate_json(
                prompt=prompt_text,
                max_tokens=metadata.get('max_tokens', 3000),
                temperature=metadata.get('temperature', 0.4),
                task=AITaskType.BIAS_CHECK,
                model=model_enum,
                provider=provider_enum,
                system=system_context,
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
            db.session.rollback()
            logger.error(f"TASK {self.request.id}: Bias check failed - {e}", exc_info=True)

            # Update task as failed
            task = BackgroundTask.query.get(task_id)
            if task:
                task.status = 'failed'
                task.completed_at = now_utc()
                task.error_message = 'Something went wrong. Please try again.'
                db.session.commit()

            return {"status": "failed", "message": str(e)}


# =========================================================================
# Counter-Evidence Generation (Companion)
# =========================================================================

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
            db.session.rollback()
            logger.error(f"TASK {self.request.id}: Argos deep analysis failed - {e}", exc_info=True)

            task = BackgroundTask.query.get(task_id)
            if task:
                task.status = 'failed'
                task.completed_at = now_utc()
                task.error_message = 'Something went wrong. Please try again.'
                db.session.commit()

            return {"status": "failed", "message": str(e)}


# =========================================================================
# Checklist Item AI Analysis (Run Prompt)
# =========================================================================

# =========================================================================
# AI Research Assistant (Challenge / Elaboration / Fact-Check)
# =========================================================================

# Bounded so a hung provider call cannot leave the row in 'running' forever.
# Without a limit, nothing ever reconciled a stalled task: the row stayed
# 'running' until a later request superseded it, and the UI had no way to learn
# the truth. Limits live in Config (env-overridable) and are shared with the
# browser's poll budget so both sides give up at the same point.
AI_ASSIST_SOFT_TIME_LIMIT = Config.AI_ASSIST_SOFT_TIME_LIMIT
AI_ASSIST_HARD_TIME_LIMIT = Config.AI_ASSIST_HARD_TIME_LIMIT


@celery.task(bind=True,
             soft_time_limit=AI_ASSIST_SOFT_TIME_LIMIT,
             time_limit=AI_ASSIST_HARD_TIME_LIMIT)
def ai_research_assist_task(self, task_id, user_id, mode, question_text, answer_text,
                            company_name, use_google_search, analysis_id, item_id):
    """
    Celery background task for AI Research Assistant modes
    (Challenge, Elaboration, Fact-Check).

    Args:
        task_id: BackgroundTask ID for status tracking
        user_id: User ID for token tracking
        mode: 'challenge' | 'elaboration' | 'factcheck'
        question_text: The research question being answered
        answer_text: User's answer text
        company_name: Company name for context
        use_google_search: Whether to enable Google Search grounding
        analysis_id: Optional ChecklistAnalysis ID (for feedback tracking)
        item_id: Optional ChecklistItem ID (for feedback tracking)
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

            # 2. CALL AI RESEARCH ASSISTANT SERVICE
            context_data = {'company_name': company_name}

            if mode == 'challenge':
                ai_response = ai_research_assistant.generate_challenge(
                    question_text=question_text,
                    user_answer=answer_text,
                    context_data=context_data,
                    google_search=use_google_search
                )
            elif mode == 'elaboration':
                ai_response = ai_research_assistant.generate_elaboration(
                    question_text=question_text,
                    user_answer=answer_text,
                    context_data=context_data,
                    google_search=use_google_search
                )
            elif mode == 'factcheck':
                ai_response = ai_research_assistant.generate_factcheck(
                    question_text=question_text,
                    user_answer=answer_text,
                    context_data=context_data,
                    google_search=use_google_search
                )
            else:
                raise ValueError(f"Invalid mode '{mode}'")

            if not ai_response.success:
                raise ValueError(ai_response.error or 'AI service failed')

            # 3. STORE FEEDBACK RECORD
            feedback_record = AIResearchFeedback(
                user_id=user_id,
                analysis_id=analysis_id,
                item_id=item_id,
                company_name=company_name,
                mode=mode,
                question_text=question_text,
                user_answer=answer_text,
                ai_response=ai_response.response_text,
                tokens_used=ai_response.tokens_used,
                feedback=None,
                prompt_version=ai_response.metadata.get('template_version') if ai_response.metadata else None,
                provider=ai_response.metadata.get('provider', 'gemini') if ai_response.metadata else 'gemini',
                model=ai_response.metadata.get('model', 'gemini-flash') if ai_response.metadata else 'gemini-flash'
            )
            db.session.add(feedback_record)
            db.session.flush()

            # 4. TRACK TOKEN USAGE
            user = User.query.get(user_id)
            if user:
                user.increment_ai_tokens(ai_response.tokens_used)

            # 5. UPDATE TASK AS COMPLETED
            task.status = 'completed'
            task.completed_at = now_utc()
            task.result = json.dumps({
                'response': ai_response.response_text,
                'mode': mode,
                'tokens_used': ai_response.tokens_used,
                'feedback_id': feedback_record.id
            })
            db.session.commit()

            logger.info(
                f"TASK {self.request.id}: AI research assist ({mode}) completed, "
                f"feedback_id={feedback_record.id}, tokens={ai_response.tokens_used}"
            )
            return {"status": "success", "tokens_used": ai_response.tokens_used}

        except SoftTimeLimitExceeded:
            # Caught before the generic handler so the user gets a real reason
            # rather than an empty exception string.
            db.session.rollback()
            message = (
                f'Analysis timed out after {AI_ASSIST_SOFT_TIME_LIMIT}s. '
                'The AI provider did not respond in time — please try again.'
            )
            logger.error(f"TASK {self.request.id}: AI research assist ({mode}) hit soft time limit")

            task = BackgroundTask.query.get(task_id)
            if task:
                task.status = 'failed'
                task.completed_at = now_utc()
                task.error_message = message
                db.session.commit()

            return {"status": "failed", "message": message}

        except Exception as e:
            db.session.rollback()
            logger.error(f"TASK {self.request.id}: AI research assist ({mode}) failed - {e}", exc_info=True)

            task = BackgroundTask.query.get(task_id)
            if task:
                task.status = 'failed'
                task.completed_at = now_utc()
                task.error_message = 'Something went wrong. Please try again.'
                db.session.commit()

            return {"status": "failed", "message": str(e)}
