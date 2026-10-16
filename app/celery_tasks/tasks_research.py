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

import logging

from app import db
from app.celery_tasks.base import TaskFailed, background_task
from app.models import User, ResearchProject, BiasCheckResult, AIResearchFeedback
from config import Config

from app.services.ai import ai_service
from app.services.ai.prompt_service import prompt_service, resolve_model_provider
from app.services.ai.config import AITaskType
from app.services.argos import ArgosService
from app.services.ai_research_assistant import ai_research_assistant
from app.services.research_data_service import ResearchDataService

logger = logging.getLogger(__name__)


# Constants for bias check
BIAS_CHECK_PROMPT_CATEGORY = "research"
BIAS_CHECK_PROMPT_NAME = "bias_check"


@background_task()
def bias_check_task(self, task, user_id, project_id):
    """
    Celery background task for cognitive bias analysis.

    Args:
        task: BackgroundTask row for status tracking (passed by @background_task)
        user_id: User ID for token tracking
        project_id: ResearchProject ID to analyze
    """
    # 1. GET PROJECT AND DATA
    project = ResearchProject.query.get(project_id)
    if not project:
        raise ValueError(f"Project {project_id} not found")

    thesis_text = ResearchDataService.get_all_text(project, include_metadata=True)
    word_count = len(thesis_text.split())

    if word_count < 200:
        raise TaskFailed(f"Insufficient research text. Found {word_count} words, minimum is 200.")

    company_name = project.company.name if project.company else project.project_name
    sector = project.company.sector.display_name if project.company and project.company.sector else None

    # 2. LOAD PROMPT AND CALL AI
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

    # 3. ESTIMATE TOKENS AND TRACK USAGE
    tokens_estimate = len(prompt_text) // 4 + len(str(result)) // 4

    user = User.query.get(user_id)
    if user:
        user.increment_ai_tokens(tokens_estimate)

    # 4. SAVE BIAS CHECK RESULT
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

    logger.info(f"TASK {self.request.id}: Bias check score={bias_result.overall_score}")
    return {
        'result_id': bias_result.id,
        'overall_score': bias_result.overall_score,
        'tokens_used': tokens_estimate
    }


# =========================================================================
# Argos Deep Analysis (Background)
# =========================================================================

@background_task()
def argos_deep_analysis_task(self, task, user_id, company_id, step_type, step_context, current_text, include_companion_warnings):
    """
    Run Argos deep analysis asynchronously.

    Args:
        task: BackgroundTask row for status tracking (passed by @background_task)
        user_id: User ID
        company_id: Company ID to analyze
        step_type: Research step type (checklist, free_research, thesis, completion)
        step_context: Optional context dict for the step
        current_text: Current research text for semantic matching
        include_companion_warnings: Whether to prepend companion warnings to current_text
    """
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

    logger.info(f"TASK {self.request.id}: Argos deep analysis for company {company_id}")
    return result.to_dict()


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


@background_task(
    soft_time_limit=AI_ASSIST_SOFT_TIME_LIMIT,
    time_limit=AI_ASSIST_HARD_TIME_LIMIT,
    timeout_message=(f'Analysis timed out after {AI_ASSIST_SOFT_TIME_LIMIT}s. '
                     'The AI provider did not respond in time — please try again.'),
)
def ai_research_assist_task(self, task, user_id, mode, question_text, answer_text,
                            company_name, use_google_search, analysis_id, item_id):
    """
    Celery background task for AI Research Assistant modes
    (Challenge, Elaboration, Fact-Check).

    Args:
        task: BackgroundTask row for status tracking (passed by @background_task)
        user_id: User ID for token tracking
        mode: 'challenge' | 'elaboration' | 'factcheck'
        question_text: The research question being answered
        answer_text: User's answer text
        company_name: Company name for context
        use_google_search: Whether to enable Google Search grounding
        analysis_id: Optional ChecklistAnalysis ID (for feedback tracking)
        item_id: Optional ChecklistItem ID (for feedback tracking)
    """
    # 1. CALL AI RESEARCH ASSISTANT SERVICE
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

    # 2. STORE FEEDBACK RECORD
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

    # 3. TRACK TOKEN USAGE
    user = User.query.get(user_id)
    if user:
        user.increment_ai_tokens(ai_response.tokens_used)

    logger.info(
        f"TASK {self.request.id}: AI research assist ({mode}) "
        f"feedback_id={feedback_record.id}, tokens={ai_response.tokens_used}"
    )
    return {
        'response': ai_response.response_text,
        'mode': mode,
        'tokens_used': ai_response.tokens_used,
        'feedback_id': feedback_record.id
    }
