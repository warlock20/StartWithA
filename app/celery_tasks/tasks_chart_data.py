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

import logging

from app.celery_tasks.base import background_task
from app.models import Transaction
from app.services.portfolio_data_extractor import PortfolioDataExtractor

logger = logging.getLogger(__name__)


@background_task()
def portfolio_chart_data_task(self, task, user_id, time_periods=12):
    """
    Celery task to compute Performance vs Cost chart data.

    Fetches historical + current prices (potential API calls) and
    replays transactions to build the chart arrays.

    No AI tokens consumed — this is purely data retrieval.

    Args:
        task: BackgroundTask row for status tracking (passed by @background_task)
        user_id: User whose portfolio to compute
        time_periods: Number of months (1, 3, 6, 12, 24, 36)
    """
    logger.info(f"CHART_DATA {self.request.id}: Computing chart data for user {user_id}, {time_periods} months")

    extractor = PortfolioDataExtractor(user_id=user_id)
    transactions = Transaction.query.filter_by(user_id=user_id).all()
    chart_data = extractor.calculate_performance_chart_data(
        transactions, time_periods=time_periods
    )
    return {'chart_data': chart_data, 'time_periods': time_periods}
