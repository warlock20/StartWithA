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
Checkpoint Analysis Celery Tasks

Daily scheduled task that analyzes active DestinationCheckpoints using AI.
Evaluates whether investment milestones are on track based on research context
and stores results as AIInsight records.

Scheduled: Daily at 20:00 UTC via Celery Beat.
"""

import logging

from app import db
from app.celery_tasks.base import record_job_run
from app.models import Company, User, ResearchProject
from app.services.checkpoint_analysis_service import CheckpointAnalysisService
from celery_app import celery

logger = logging.getLogger(__name__)

# One analysis: the prompt plus checkpoint_analysis.yaml's 1500 max_tokens.
ESTIMATED_TOKENS = 3000


@celery.task(bind=True)
@record_job_run('checkpoint-daily-analysis')
def analyze_all_checkpoints(self):
    """
    Daily batch analysis of active checkpoints across all users.

    Users without AI consent are skipped, and a user's remaining checkpoints
    are skipped once their token budget runs out.

    For each active checkpoint within the analysis window:
    1. Skips if already analyzed in the last 24h (dedup)
    2. Builds context from the user's research data
    3. Calls AI service for assessment
    4. Stores result as AIInsight record

    Individual checkpoint failures are logged and skipped to avoid
    one failure stopping the entire batch.
    """
    try:
        grouped = CheckpointAnalysisService.get_checkpoints_for_analysis()

        total_users = len(grouped)
        total_checkpoints = sum(len(cps) for cps in grouped.values())
        analyzed = 0
        skipped = 0
        failed = 0
        no_consent = 0
        over_budget = 0

        logger.info(
            f"Checkpoint analysis starting: {total_checkpoints} checkpoints "
            f"across {total_users} users"
        )

        for user_id, checkpoints in grouped.items():
            user = User.query.get(user_id)
            if not user:
                continue
            if not user.ai_consent_given:
                no_consent += len(checkpoints)
                continue

            for position, checkpoint in enumerate(checkpoints):
                if not user.can_use_ai_tokens(ESTIMATED_TOKENS):
                    over_budget += len(checkpoints) - position
                    break
                try:
                    # Dedup: skip if analyzed recently
                    if CheckpointAnalysisService.has_recent_analysis(checkpoint.id):
                        skipped += 1
                        continue

                    company = Company.query.get(checkpoint.company_id)
                    if not company:
                        skipped += 1
                        continue

                    # Get research project for context (may be None)
                    research_project = ResearchProject.query.filter_by(
                        user_id=user_id,
                        company_id=checkpoint.company_id,
                    ).first()

                    insight = CheckpointAnalysisService.analyze_checkpoint(
                        checkpoint, company, research_project, user
                    )

                    if insight:
                        analyzed += 1
                    else:
                        failed += 1

                except Exception as e:
                    failed += 1
                    logger.error(
                        f"Checkpoint analysis failed for checkpoint {checkpoint.id} "
                        f"(user={user_id}, company={checkpoint.company_id}): {e}",
                        exc_info=True,
                    )
                    db.session.rollback()

            # Commit per-user batch
            try:
                db.session.commit()
            except Exception as e:
                logger.error(f"Failed to commit for user {user_id}: {e}", exc_info=True)
                db.session.rollback()

        logger.info(
            f"Checkpoint analysis complete: {analyzed} analyzed, "
            f"{skipped} skipped (dedup), {failed} failed, "
            f"{no_consent} skipped (no AI consent), {over_budget} skipped (over token budget)"
        )

        return {
            'status': 'success',
            'total_checkpoints': total_checkpoints,
            'analyzed': analyzed,
            'skipped': skipped,
            'failed': failed,
            'no_consent': no_consent,
            'over_budget': over_budget,
        }

    except Exception as e:
        db.session.rollback()
        logger.error(f"Checkpoint analysis batch failed: {e}", exc_info=True)
        return {'status': 'failed', 'error': str(e)}
