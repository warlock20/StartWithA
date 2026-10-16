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
"""

import json
import logging
from functools import wraps

from celery.exceptions import SoftTimeLimitExceeded

from app import create_app, db
from app.models import BackgroundTask
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
