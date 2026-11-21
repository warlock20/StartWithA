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
Hourly dispatcher for per-user background monitors (#436).

Scheduled: every hour on the hour via Celery Beat. Queues run_monitor_task for each
user whose monitor is due. Deliberately not exported from app/celery_tasks/__init__.py:
dispatch_due_monitors uses BackgroundTaskService, which imports that package, so an
export would create an import cycle. Celery finds this module through the include list.
"""

from app.celery_tasks.base import record_job_run
from app.services.monitor_schedule import dispatch_due_monitors
from celery_app import celery


@celery.task(bind=True)
@record_job_run('dispatch-user-monitors')
def dispatch_user_monitors(self):
    return {'status': 'success', **dispatch_due_monitors()}
