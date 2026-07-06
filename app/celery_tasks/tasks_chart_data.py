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
Portfolio Chart Data Celery Task

Background task for computing Performance vs Cost chart data.
Moves price-fetching API calls out of the request path.
"""

import json
import logging
from app import db, create_app
from celery_app import celery
from app.models import BackgroundTask
from app.utils.time_utils import now_utc

logger = logging.getLogger(__name__)


@celery.task(bind=True)
def portfolio_chart_data_task(self, task_id, user_id, time_periods=12):
    """
    Celery task to compute Performance vs Cost chart data.

    Fetches historical + current prices (potential API calls) and
    replays transactions to build the chart arrays.

    No AI tokens consumed — this is purely data retrieval.

    Args:
        task_id: BackgroundTask ID for status tracking
        user_id: User whose portfolio to compute
        time_periods: Number of months (1, 3, 6, 12, 24, 36)
    """
    app = create_app()
    with app.app_context():
        task = BackgroundTask.query.get(task_id)
        if not task:
            logger.error(f"CHART_DATA {self.request.id}: BackgroundTask {task_id} not found")
            return json.dumps({"status": "failed", "message": "Task record not found"})

        try:
            # 1. Update status to running
            task.status = 'running'
            task.started_at = now_utc()
            db.session.commit()

            logger.info(f"CHART_DATA {self.request.id}: Computing chart data for user {user_id}, {time_periods} months")

            # 2. Compute chart data (this is where the API calls happen)
            from app.services.portfolio_data_extractor import PortfolioDataExtractor
            from app.models import Transaction

            extractor = PortfolioDataExtractor(user_id=user_id)
            transactions = Transaction.query.filter_by(user_id=user_id).all()
            chart_data = extractor.calculate_performance_chart_data(
                transactions, time_periods=time_periods
            )

            # 3. Save result
            task.status = 'completed'
            task.completed_at = now_utc()
            task.result = json.dumps({
                'chart_data': chart_data,
                'time_periods': time_periods
            })
            db.session.commit()

            logger.info(f"CHART_DATA {self.request.id}: Completed for user {user_id}")
            return json.dumps({"status": "success"})

        except Exception as e:
            logger.error(f"CHART_DATA {self.request.id}: Failed - {e}", exc_info=True)

            task.status = 'failed'
            task.completed_at = now_utc()
            task.error_message = str(e)
            db.session.commit()

            return json.dumps({"status": "failed", "message": str(e)})
