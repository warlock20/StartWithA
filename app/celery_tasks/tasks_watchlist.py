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
Watchlist target check: daily scheduled task that compares each watchlist
project's valuation target with the latest price, market cap or EV.

Scheduled: Daily at 20:30 UTC via Celery Beat.
"""

from app.celery_tasks.base import record_job_run
from app.services.watchlist_targets import check_all_targets
from celery_app import celery


@celery.task(bind=True)
@record_job_run('watchlist-target-check')
def check_watchlist_targets(self):
    return {'status': 'success', **check_all_targets()}
