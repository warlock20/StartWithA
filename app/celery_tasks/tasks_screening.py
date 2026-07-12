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

import json
import logging

from app import db, create_app
from app.models import BackgroundTask, User
from celery_app import celery

from app.services.ai import ai_service
from app.services.ai.prompt_service import prompt_service
from app.services.ai.config import AITaskType
from app.services.screening_analysis_service import ScreeningAnalysisService
from app.utils.time_utils import now_utc

logger = logging.getLogger(__name__)

SCREENING_PROMPT_CATEGORY = "screening"
SCREENING_PROMPT_NAME = "screening_analysis"


@celery.task(bind=True)
def screening_analysis_task(self, task_id, user_id):
    """
    Celery background task for screening analysis.

    Args:
        task_id: BackgroundTask ID for status tracking
        user_id: User ID for token tracking
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

            # 2. GATHER SCREENING DATA
            can_analyze, stats = ScreeningAnalysisService.has_sufficient_data(user_id)
            if not can_analyze:
                raise ValueError(
                    f"Insufficient data. Found {stats['completed_sessions']} completed "
                    f"sessions, minimum is {stats['minimum_required']}."
                )

            data = ScreeningAnalysisService.gather_screening_data(user_id)
            screening_text = ScreeningAnalysisService.format_for_llm(data)

            logger.info(
                f"TASK {self.request.id}: Running screening analysis for user {user_id} "
                f"({data['total_sessions']} sessions, {data['total_killed']} killed)"
            )

            # 3. LOAD PROMPT AND CALL AI
            prompt_data = prompt_service.get_prompt_with_metadata(
                category=SCREENING_PROMPT_CATEGORY,
                name=SCREENING_PROMPT_NAME,
                screening_data=screening_text,
            )

            prompt_text = prompt_data['prompt']
            metadata = prompt_data.get('metadata', {})
            system_context = prompt_data.get('system_context')

            result = ai_service.generate_json(
                prompt=prompt_text,
                max_tokens=metadata.get('max_tokens', 4000),
                temperature=metadata.get('temperature', 0.3),
                task=AITaskType.CHECKLIST_ANALYSIS,
                system=system_context,
            )

            if not result:
                raise ValueError("AI analysis returned no result")

            # 4. ESTIMATE TOKENS AND TRACK USAGE
            tokens_estimate = len(prompt_text) // 4 + len(str(result)) // 4

            user = User.query.get(user_id)
            if user:
                user.increment_ai_tokens(tokens_estimate)

            # 5. STORE RESULT IN TASK
            task.status = 'completed'
            task.completed_at = now_utc()
            task.result = json.dumps(result)
            db.session.commit()

            logger.info(
                f"TASK {self.request.id}: Screening analysis completed, "
                f"tokens={tokens_estimate}"
            )
            return {"status": "success", "tokens_used": tokens_estimate}

        except Exception as e:
            logger.error(
                f"TASK {self.request.id}: Screening analysis failed - {e}",
                exc_info=True
            )

            task = BackgroundTask.query.get(task_id)
            if task:
                task.status = 'failed'
                task.completed_at = now_utc()
                task.error_message = str(e)
                db.session.commit()

            return {"status": "failed", "message": str(e)}
