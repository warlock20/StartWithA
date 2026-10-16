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
Screening Analysis Celery Task

Background task for AI-powered kill checklist analysis.
Surfaces dealbreaker patterns, red-flag themes, and refinement suggestions.
"""

import logging

from app.celery_tasks.base import TaskFailed, background_task
from app.models import User

from app.services.ai import ai_service
from app.services.ai.prompt_service import prompt_service, resolve_model_provider
from app.services.ai.config import AITaskType
from app.services.screening_analysis_service import ScreeningAnalysisService

logger = logging.getLogger(__name__)

SCREENING_PROMPT_CATEGORY = "screening"
SCREENING_PROMPT_NAME = "screening_analysis"


@background_task()
def screening_analysis_task(self, task, user_id):
    """
    Celery background task for screening analysis.

    Args:
        task: BackgroundTask row for status tracking (passed by @background_task)
        user_id: User ID for token tracking
    """
    # 1. GATHER SCREENING DATA
    can_analyze, stats = ScreeningAnalysisService.has_sufficient_data(user_id)
    if not can_analyze:
        raise TaskFailed(
            f"Insufficient data. Found {stats['completed_sessions']} completed "
            f"sessions, minimum is {stats['minimum_required']}."
        )

    data = ScreeningAnalysisService.gather_screening_data(user_id)
    screening_text = ScreeningAnalysisService.format_for_llm(data)

    logger.info(
        f"TASK {self.request.id}: Running screening analysis for user {user_id} "
        f"({data['total_sessions']} sessions, {data['total_killed']} killed)"
    )

    # 2. LOAD PROMPT AND CALL AI
    prompt_data = prompt_service.get_prompt_with_metadata(
        category=SCREENING_PROMPT_CATEGORY,
        name=SCREENING_PROMPT_NAME,
        screening_data=screening_text,
    )

    prompt_text = prompt_data['prompt']
    metadata = prompt_data.get('metadata', {})
    system_context = prompt_data.get('system_context')
    model_enum, provider_enum = resolve_model_provider(
        metadata, user_id=user_id, prompt_category=SCREENING_PROMPT_CATEGORY,
    )

    result = ai_service.generate_json(
        prompt=prompt_text,
        max_tokens=metadata.get('max_tokens', 4000),
        temperature=metadata.get('temperature', 0.3),
        task=AITaskType.CHECKLIST_ANALYSIS,
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

    logger.info(f"TASK {self.request.id}: Screening analysis tokens={tokens_estimate}")
    return result
