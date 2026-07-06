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
GDPR Data Retention Celery Tasks

Periodic tasks for anonymizing old AI interaction logs per GDPR Art. 5(1)(e).
Targets raw Q&A data only — derived intelligence (ARGOS, insights) is kept.
"""

import logging
from datetime import timedelta

from app import db, create_app
from celery_app import celery
from app.models import AIResearchFeedback
from app.models.prompt_management import PromptUsageLog
from app.utils.time_utils import now_utc

logger = logging.getLogger(__name__)

ANONYMIZATION_DAYS = 90


@celery.task(bind=True)
def anonymize_ai_interactions(self):
    """
    Anonymize AI interaction records older than 90 days.

    Targets:
    - AIResearchFeedback: question_text, user_answer, ai_response → '[anonymized]'
    - PromptUsageLog: context_data → None

    Preserves: mode, feedback, tokens_used, provider, model, timestamps
    (aggregated metrics remain useful for analytics without PII).
    """
    app = create_app()
    with app.app_context():
        try:
            cutoff = now_utc() - timedelta(days=ANONYMIZATION_DAYS)

            # --- AIResearchFeedback: anonymize raw Q&A text ---
            feedback_count = AIResearchFeedback.query.filter(
                AIResearchFeedback.created_at < cutoff,
                AIResearchFeedback.question_text != '[anonymized]',
            ).update({
                AIResearchFeedback.question_text: '[anonymized]',
                AIResearchFeedback.user_answer: '[anonymized]',
                AIResearchFeedback.ai_response: '[anonymized]',
                AIResearchFeedback.revised_answer: None,
                AIResearchFeedback.company_name: None,
            }, synchronize_session=False)

            # --- PromptUsageLog: strip context_data (may contain user input) ---
            prompt_count = PromptUsageLog.query.filter(
                PromptUsageLog.created_at < cutoff,
                PromptUsageLog.context_data.isnot(None),
            ).update({
                PromptUsageLog.context_data: None,
            }, synchronize_session=False)

            db.session.commit()

            logger.info(
                f"GDPR retention: anonymized {feedback_count} AI feedback records, "
                f"cleared {prompt_count} prompt context records (cutoff: {cutoff.date()})"
            )
            return {
                'status': 'success',
                'feedback_anonymized': feedback_count,
                'prompt_contexts_cleared': prompt_count,
            }

        except Exception as e:
            db.session.rollback()
            logger.error(f"GDPR retention job failed: {e}", exc_info=True)
            return {'status': 'failed', 'error': str(e)}
