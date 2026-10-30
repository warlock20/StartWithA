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
Shared scaffolding for Celery tasks tracked by a BackgroundTask row.

    @background_task()
    def screening_analysis_task(self, task, user_id):
        if not enough_data:
            raise TaskFailed('Insufficient data. ...')   # shown to the user
        return result                                     # stored as task.result

The decorator builds the app context, marks the row running, stores the
return value as JSON and marks it completed. TaskFailed fails the row with its
message; any other exception is rolled back, logged with its traceback and
fails the row with a generic message, so internals never reach the UI.

Scheduled (beat) jobs have no BackgroundTask row. record_job_run gives them
the same app-context scaffolding and writes a ScheduledJobRun row per run:

    @celery.task(bind=True)
    @record_job_run('gdpr-anonymize-ai-interactions')
    def anonymize_ai_interactions(self):
        ...
"""

import json
import logging
from contextlib import nullcontext
from functools import wraps

from celery.exceptions import SoftTimeLimitExceeded
from flask import has_app_context

from app import create_app, db
from app.models import BackgroundTask
from app.services.scheduled_jobs import finish_run, start_run
from app.utils.time_utils import now_utc
from celery_app import celery

logger = logging.getLogger(__name__)

GENERIC_FAILURE = 'Something went wrong. Please try again.'


class TaskFailed(Exception):
    """Fail a background task with a message the user may see."""


def background_task(timeout_message=None, **celery_options):
    """Register fn(self, task, *args) as a Celery task called with (task_id, *args).

    timeout_message replaces the default message shown when soft_time_limit hits.
    """
    soft_limit = celery_options.get('soft_time_limit')
    timeout_message = timeout_message or f'Timed out after {soft_limit}s. Please try again.'

    def decorator(fn):
        @celery.task(bind=True, name=f'{fn.__module__}.{fn.__name__}', **celery_options)
        @wraps(fn)
        def run(self, task_id, *args, **kwargs):
            app = create_app()
            with app.app_context():
                task = db.session.get(BackgroundTask, task_id)
                if not task:
                    logger.error(f"TASK {self.request.id}: BackgroundTask {task_id} not found")
                    return {'status': 'failed', 'message': 'Task not found'}

                task.status = 'running'
                task.started_at = now_utc()
                db.session.commit()

                try:
                    result = fn(self, task, *args, **kwargs)
                except TaskFailed as e:
                    db.session.rollback()
                    logger.info(f"TASK {self.request.id}: {fn.__name__} failed: {e}")
                    return _fail(task_id, str(e))
                except SoftTimeLimitExceeded:
                    db.session.rollback()
                    logger.error(f"TASK {self.request.id}: {fn.__name__} hit its {soft_limit}s soft time limit")
                    return _fail(task_id, timeout_message)
                except Exception:
                    db.session.rollback()
                    logger.exception(f"TASK {self.request.id}: {fn.__name__} failed")
                    return _fail(task_id, GENERIC_FAILURE)

                task.status = 'completed'
                task.completed_at = now_utc()
                task.result = json.dumps(result) if result is not None else None
                db.session.commit()
                logger.info(f"TASK {self.request.id}: {fn.__name__} completed")
                return {'status': 'completed'}

        return run

    return decorator


def _fail(task_id, message):
    task = db.session.get(BackgroundTask, task_id)
    if task:
        task.status = 'failed'
        task.completed_at = now_utc()
        task.error_message = message
        db.session.commit()
    return {'status': 'failed', 'message': message}


def record_job_run(job_name):
    """Record each run of a scheduled task as a ScheduledJobRun under `job_name`, its beat_schedule key.

    Goes under @celery.task and leaves the task's signature alone: beat calls it
    with no arguments, and a manual run passes triggered_by='manual' and
    triggered_by_user_id as kwargs, which are taken off here before the task
    sees them. (Celery checks call arguments against the wrapper's own
    (*args, **kwargs), not the wrapped function.)

    Provides the app context, so the task body needn't build one. A raised
    exception fails the run and is re-raised; so does a returned
    {'status': 'failed', 'error': ...}, the convention of tasks that catch
    their own errors.
    """
    def decorator(fn):
        @wraps(fn)
        def run(*args, triggered_by='schedule', triggered_by_user_id=None, **kwargs):
            with nullcontext() if has_app_context() else create_app().app_context():
                run_id = start_run(job_name, triggered_by, triggered_by_user_id)
                try:
                    result = fn(*args, **kwargs)
                except Exception as e:
                    db.session.rollback()
                    finish_run(run_id, 'failed', str(e) or type(e).__name__)
                    raise

                if isinstance(result, dict) and result.get('status') == 'failed':
                    finish_run(run_id, 'failed', result.get('error'))
                else:
                    finish_run(run_id, 'success')
                return result

        run.scheduled_job_name = job_name
        return run

    return decorator
