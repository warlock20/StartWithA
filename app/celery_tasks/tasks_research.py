# Investment Checklist Platform
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

Background tasks for competitor analysis, bias check, and argos deep analysis.
"""

import json
import logging
import os

import fitz
from flask import current_app

from app import db, create_app
from app.models import Company, BackgroundTask, WorkSession, User, ResearchProject, BiasCheckResult, ChecklistItem, ChecklistAnalysis, CompanyResource, AIResearchFeedback
from celery_app import celery

from app.services.ai import generate_text, ai_service
from app.services.ai.prompt_service import get_competitor_analysis_prompt, prompt_service
from app.services.ai.config import AITaskType
from app.services.argos import ArgosService
from app.services.ai_research_assistant import ai_research_assistant
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
            competitor_analysis = generate_text(analysis_prompt, max_tokens=2000)

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


# =========================================================================
# Checklist Item AI Analysis (Run Prompt)
# =========================================================================

@celery.task(bind=True)
def checklist_item_analyze_task(self, task_id, user_id, analysis_id, item_id, selected_document_ids):
    """
    Celery background task for checklist item AI analysis (Run Prompt).

    Extracts text from selected documents, builds the prompt from YAML template,
    calls the LLM, and stores the result in BackgroundTask.

    Args:
        task_id: BackgroundTask ID for status tracking
        user_id: User ID for token tracking
        analysis_id: ChecklistAnalysis session ID
        item_id: ChecklistItem ID
        selected_document_ids: List of CompanyResource IDs to use as context
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

            # 2. GET CHECKLIST ITEM AND ITS LLM PROMPT
            session = ChecklistAnalysis.query.get(analysis_id)
            if not session:
                raise ValueError(f"ChecklistAnalysis {analysis_id} not found")

            item = ChecklistItem.query.get(item_id)
            if not item:
                raise ValueError(f"ChecklistItem {item_id} not found")

            llm_question = item.llm_prompt
            if not llm_question:
                raise ValueError(f"ChecklistItem {item_id} has no llm_prompt defined")

            # 3. EXTRACT TEXT FROM SELECTED DOCUMENTS
            aggregated_text_content = ""

            if selected_document_ids:
                company_documents = CompanyResource.query.filter(
                    CompanyResource.id.in_(selected_document_ids),
                    CompanyResource.company_id == session.company_id,
                    CompanyResource.resource_type == 'file'
                ).all()

                upload_folder = current_app.config['UPLOAD_FOLDER']

                for doc in company_documents:
                    try:
                        full_file_path = os.path.join(upload_folder, doc.stored_filename)
                        if not os.path.exists(full_file_path):
                            aggregated_text_content += f"\n\n--- ERROR: File not found: {doc.original_filename} ---"
                            continue

                        if doc.original_filename.lower().endswith('.pdf'):
                            with fitz.open(full_file_path) as pdf_doc:
                                for page in pdf_doc:
                                    aggregated_text_content += page.get_text("text") + "\n"
                        elif doc.original_filename.lower().endswith('.txt'):
                            with open(full_file_path, 'r', encoding='utf-8') as txt_file:
                                aggregated_text_content += txt_file.read() + "\n"
                        else:
                            aggregated_text_content += f"\n\n--- Skipped unsupported file type: {doc.original_filename} ---"
                    except Exception as e:
                        aggregated_text_content += f"\n\n--- ERROR processing {doc.original_filename}: {str(e)} ---"
                        logger.warning(f"TASK {self.request.id}: Error processing document {doc.original_filename}: {e}")

            # 4. BUILD PROMPT FROM YAML AND CALL AI
            company = session.company
            prompt_for_llm = prompt_service.get_prompt(
                'research',
                'checklist_item_analyze',
                context=aggregated_text_content if aggregated_text_content.strip() else "No documents provided.",
                question=llm_question,
                company_name=company.name,
                ticker_symbol=company.ticker_symbol,
                sector=company.sector.display_name if company.sector else 'N/A',
                industry=company.industry or 'N/A'
            )

            logger.info(f"TASK {self.request.id}: Running checklist item analysis for item {item_id} in session {analysis_id}")
            ai_suggestion = generate_text(prompt_for_llm, google_search=True)

            # 5. ESTIMATE TOKENS AND TRACK USAGE
            tokens_estimate = len(prompt_for_llm) // 4 + len(ai_suggestion) // 4

            user = User.query.get(user_id)
            if user:
                user.increment_ai_tokens(tokens_estimate)

            # 6. UPDATE TASK AS COMPLETED
            task.status = 'completed'
            task.completed_at = now_utc()
            task.result = json.dumps({
                'ai_suggestion': ai_suggestion,
                'received_prompt': llm_question,
                'tokens_used': tokens_estimate
            })
            db.session.commit()

            logger.info(f"TASK {self.request.id}: Checklist item analysis completed for item {item_id}")
            return {"status": "success", "tokens_used": tokens_estimate}

        except Exception as e:
            logger.error(f"TASK {self.request.id}: Checklist item analysis failed - {e}", exc_info=True)

            task = BackgroundTask.query.get(task_id)
            if task:
                task.status = 'failed'
                task.completed_at = now_utc()
                task.error_message = str(e)
                db.session.commit()

            return {"status": "failed", "message": str(e)}


# =========================================================================
# AI Research Assistant (Challenge / Elaboration / Fact-Check)
# =========================================================================

@celery.task(bind=True)
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

        except Exception as e:
            logger.error(f"TASK {self.request.id}: AI research assist ({mode}) failed - {e}", exc_info=True)

            task = BackgroundTask.query.get(task_id)
            if task:
                task.status = 'failed'
                task.completed_at = now_utc()
                task.error_message = str(e)
                db.session.commit()

            return {"status": "failed", "message": str(e)}
