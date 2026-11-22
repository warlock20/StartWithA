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
Background monitor Celery task.

One generic task runs a single monitor for a single user. The hourly
dispatcher (or Run now) creates the BackgroundTask row with task_type
'monitor:<key>' and queues run_monitor_task; MONITOR_RUNNERS maps each
monitor key to the function that does the work.
"""

import logging

from app import db
from app.celery_tasks.base import TaskFailed, background_task
from app.models import User
from app.services.checkpoint_analysis_service import CheckpointAnalysisService
from app.services.exit_watch.run import run_exit_watch
from app.services.monitor_registry import MONITOR_RUN_SOFT_LIMIT, dedup_window, expiry_window, get_monitor

logger = logging.getLogger(__name__)

MONITOR_RUN_HARD_LIMIT = MONITOR_RUN_SOFT_LIMIT + 120  # room to roll back and report the timeout
TIMEOUT_MESSAGE = 'Stopped at the 30-minute time limit. The next run picks up what was not finished.'


def _run_checkpoint_analysis(user, monitor):
    return CheckpointAnalysisService.analyze_user_checkpoints(
        user, dedup_window(monitor), monitor.estimated_tokens, expiry_window(monitor)
    )


MONITOR_RUNNERS = {
    'checkpoint_analysis': _run_checkpoint_analysis,
    'exit_criteria_watch': run_exit_watch,
}


@background_task(timeout_message=TIMEOUT_MESSAGE, soft_time_limit=MONITOR_RUN_SOFT_LIMIT,
                 time_limit=MONITOR_RUN_HARD_LIMIT)
def run_monitor_task(self, task, user_id: int, monitor_key: str):
    """Run one monitor for one user and return its summary dict."""
    monitor = get_monitor(monitor_key)
    runner = MONITOR_RUNNERS.get(monitor_key)
    if monitor is None or runner is None:
        raise TaskFailed('This monitor no longer exists.')

    user = db.session.get(User, user_id)
    if user is None:
        raise TaskFailed('User not found.')
    if not user.ai_consent_given:
        raise TaskFailed('AI features are off, so nothing was checked.')

    return runner(user, monitor)
