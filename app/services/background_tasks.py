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
Background task service for LLM operations
Uses Celery for robust task processing
"""

import uuid
import json
from datetime import timedelta
from flask import session
from sqlalchemy import and_, or_
from app import db
from app.models import BackgroundTask
from app.utils.time_utils import now_utc
import logging
from app.celery_tasks import portfolio_ai_analysis_task
from app.celery_tasks import portfolio_chart_data_task
from app.celery_tasks import bias_check_task
from app.celery_tasks import argos_deep_analysis_task
from app.celery_tasks import portfolio_import_task
from app.celery_tasks import ai_research_assist_task
from app.celery_tasks import screening_analysis_task
from app.celery_tasks import companion_ask_task

logger = logging.getLogger(__name__)

# Raw Celery task ids kept per session for owns_celery_task; older ones drop off.
MAX_REMEMBERED_CELERY_TASKS = 20

# A pending task younger than this is reused instead of starting a duplicate.
# Workers normally pick tasks up within seconds; an older pending row is most
# likely one the worker never received, and reusing it would block the user.
PENDING_REUSE_SECONDS = 120


def parse_task_type(task_type: str) -> tuple:
    """
    Parse composite task_type into (category, template).

    Args:
        task_type: Task type string (e.g., 'portfolio_analysis:portfolio_raw_trade_analysis')

    Returns:
        Tuple of (category, template). If no separator found, returns (task_type, None).

    Examples:
        >>> parse_task_type('portfolio_analysis:behavioral')
        ('portfolio_analysis', 'behavioral')

        >>> parse_task_type('simple_task')
        ('simple_task', None)
    """
    parts = task_type.split(':', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return task_type, None


class BackgroundTaskService:
    @staticmethod
    def _find_active_task(user_id, task_type, **filters):
        """The user's in-flight task of this type, to reuse instead of starting a duplicate.

        Running tasks always count. Pending ones count only while recent, so a
        double-click before the worker starts the first task doesn't queue a
        second one, but a pending row the worker never picked up doesn't block
        the user forever.
        """
        recent = now_utc().replace(tzinfo=None) - timedelta(seconds=PENDING_REUSE_SECONDS)
        return BackgroundTask.query.filter_by(user_id=user_id, task_type=task_type, **filters).filter(
            or_(BackgroundTask.status == 'running',
                and_(BackgroundTask.status == 'pending', BackgroundTask.created_at >= recent))
        ).first()

    @staticmethod
    def fail_if_stalled(task_id, user_id, max_age_seconds):
        """Mark a task failed if it outlived the time limit without finishing.

        A task the worker never consumed stays 'pending' forever: the Celery
        soft limit only fires once a task is actually running, so nothing
        reconciles a job that was dropped because the worker was down. The row
        then sits there until some later request happens to supersede it, and
        meanwhile the UI waits out its whole poll budget on a job that is dead.

        Called from the status endpoint so the state self-heals on the next poll.
        """
        task = BackgroundTask.query.filter_by(id=task_id, user_id=user_id).first()
        if not task or task.status not in ('pending', 'running'):
            return

        age = (now_utc().replace(tzinfo=None) - task.created_at).total_seconds()
        if age < max_age_seconds:
            return

        task.status = 'failed'
        task.completed_at = now_utc()
        task.error_message = (
            'Task did not complete within {}s. It was never picked up by a '
            'worker, or the worker stopped before finishing.'.format(int(max_age_seconds))
        )
        db.session.commit()
        logger.warning(
            f"Reconciled stalled task {task_id} ({int(age)}s old) as failed"
        )

    @staticmethod
    def get_task_status(task_id, user_id):
        """Get current status of a background task owned by user_id.

        Returns None for a task that doesn't exist or belongs to someone else,
        so callers answer both the same way and don't reveal which it was.
        """
        task = BackgroundTask.query.filter_by(id=task_id, user_id=user_id).first()
        if not task:
            return None

        result = {
            'id': task.id,
            'status': task.status,
            'created_at': task.created_at.isoformat(),
            'started_at': task.started_at.isoformat() if task.started_at else None,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
        }

        if task.status == 'completed' and task.result:
            result['result'] = json.loads(task.result)
        elif task.status == 'failed' and task.error_message:
            result['error'] = task.error_message

        return result

    @staticmethod
    def remember_celery_task(task_id):
        """Record a raw Celery task id as started by the current session.

        Some fetches (SEC filings, financials) enqueue Celery directly without a
        BackgroundTask row, so there is no user_id to check when they're polled.
        The session keeps the ids this user started; owns_celery_task checks it.
        """
        task_ids = session.get('celery_task_ids', [])
        task_ids.append(task_id)
        session['celery_task_ids'] = task_ids[-MAX_REMEMBERED_CELERY_TASKS:]

    @staticmethod
    def owns_celery_task(task_id):
        """Whether the current session started the raw Celery task task_id."""
        return task_id in session.get('celery_task_ids', [])

    @staticmethod
    def _enqueue(user_id, task_type, celery_task, *task_args, project_id=None, reuse_active=True):
        """Create a BackgroundTask row and queue celery_task.delay(task_id, *task_args).

        With reuse_active, returns the id of the user's in-flight task of the same
        type (and project) instead of starting a duplicate.
        """
        if reuse_active:
            filters = {'project_id': project_id} if project_id is not None else {}
            existing_task = BackgroundTaskService._find_active_task(user_id, task_type, **filters)
            if existing_task:
                logger.info(f"Reusing in-flight {task_type} task {existing_task.id} for user {user_id}")
                return existing_task.id

        task_id = str(uuid.uuid4())
        db.session.add(BackgroundTask(
            id=task_id,
            user_id=user_id,
            task_type=task_type,
            project_id=project_id,
            status='pending',
        ))
        db.session.commit()

        celery_result = celery_task.delay(task_id, *task_args)
        logger.info(f"Started {task_type} task {task_id} (Celery: {celery_result.id}) for user {user_id}")
        return task_id

    @staticmethod
    def start_portfolio_analysis(user_id, template_name):
        """Portfolio AI analysis. One task per template can run at a time."""
        return BackgroundTaskService._enqueue(
            user_id, f'portfolio_analysis:{template_name}', portfolio_ai_analysis_task, user_id, template_name)

    @staticmethod
    def start_chart_data_task(user_id, time_periods=12):
        """Chart data computation (no AI tokens). One task per period length."""
        return BackgroundTaskService._enqueue(
            user_id, f'chart_data:{time_periods}', portfolio_chart_data_task, user_id, time_periods)

    @staticmethod
    def start_portfolio_import(user_id, file_path):
        """Portfolio import. One import per user at a time."""
        return BackgroundTaskService._enqueue(
            user_id, 'portfolio_import', portfolio_import_task, user_id, file_path)

    @staticmethod
    def start_bias_check(user_id, project_id):
        """Cognitive bias check. One task per project at a time."""
        return BackgroundTaskService._enqueue(
            user_id, 'bias_check', bias_check_task, user_id, project_id, project_id=project_id)

    @staticmethod
    def start_companion_ask(user_id, question, history, focus):
        """Companion agentic chat. Every question gets its own task."""
        return BackgroundTaskService._enqueue(
            user_id, 'companion_ask', companion_ask_task, user_id, question, history, focus,
            reuse_active=False)

    @staticmethod
    def start_argos_deep_analysis(user_id, company_id, step_type, step_context, current_text, include_companion_warnings):
        """Argos deep analysis (company-level). One task per user at a time."""
        return BackgroundTaskService._enqueue(
            user_id, 'argos_deep_analysis', argos_deep_analysis_task,
            user_id, company_id, step_type, step_context, current_text, include_companion_warnings)

    @staticmethod
    def start_ai_research_assist(user_id, mode, question_text, answer_text,
                                 company_name, use_google_search=False,
                                 analysis_id=None, item_id=None):
        """AI Research Assistant (Challenge/Elaboration/Fact-Check).

        A new request supersedes the user's in-flight one rather than reusing it.
        """
        task_type = 'ai_research_assist'
        BackgroundTask.query.filter(
            BackgroundTask.user_id == user_id,
            BackgroundTask.task_type == task_type,
            BackgroundTask.status.in_(['running', 'pending']),
        ).update({'status': 'failed', 'error_message': 'Superseded by new request'}, synchronize_session='fetch')
        db.session.commit()

        return BackgroundTaskService._enqueue(
            user_id, task_type, ai_research_assist_task,
            user_id, mode, question_text, answer_text, company_name, use_google_search, analysis_id, item_id,
            reuse_active=False)

    @staticmethod
    def start_screening_analysis(user_id):
        """Screening analysis. One task per user at a time."""
        return BackgroundTaskService._enqueue(
            user_id, 'screening_analysis', screening_analysis_task, user_id)
