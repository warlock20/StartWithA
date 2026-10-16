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
Portfolio Import Celery Tasks

Background task for importing transaction files (CSV/Excel) without blocking the UI.
"""

import os
import logging

from app.celery_tasks.base import TaskFailed, background_task
from app.services.portfolio_importer import PortfolioImporter, PortfolioImportError

logger = logging.getLogger(__name__)


@background_task()
def portfolio_import_task(self, task, user_id, file_path):
    """
    Celery task for importing portfolio transactions from a saved file.

    Args:
        task: BackgroundTask row for status tracking (passed by @background_task)
        user_id: User ID whose portfolio to import into
        file_path: Absolute path to the saved upload file on disk
    """
    try:
        logger.info(f"TASK {self.request.id}: Starting portfolio import for user {user_id} from {os.path.basename(file_path)}")

        importer = PortfolioImporter(user_id)
        try:
            result = importer.process_file_from_path(file_path)
        except (PortfolioImportError, ValueError) as e:
            # The importer's messages describe what's wrong with the file.
            raise TaskFailed(str(e)) from e

        logger.info(f"TASK {self.request.id}: Import completed - {result['count']} transactions, {result['companies']} companies")

        return {
            "count": result['count'],
            "skipped": result.get('skipped', 0),
            "companies": result['companies'],
            "date_range": result['date_range'],
            "message": result.get('message', f"Imported {result['count']} transactions for {result['companies']} companies")
        }

    finally:
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
                logger.info(f"TASK {self.request.id}: Cleaned up temp file {file_path}")
        except OSError as cleanup_err:
            logger.warning(f"TASK {self.request.id}: Failed to clean up {file_path}: {cleanup_err}")
