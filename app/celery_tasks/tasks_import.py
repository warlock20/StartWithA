"""
Portfolio Import Celery Tasks

Background task for importing transaction files (CSV/Excel) without blocking the UI.
"""

import json
import os
import logging
from app import db, create_app
from celery_app import celery
from app.models import BackgroundTask
from app.utils.time_utils import now_utc
from app.services.portfolio_importer import PortfolioImporter, PortfolioImportError

logger = logging.getLogger(__name__)


@celery.task(bind=True)
def portfolio_import_task(self, task_id, user_id, file_path):
    """
    Celery task for importing portfolio transactions from a saved file.

    Args:
        task_id: BackgroundTask ID for status tracking
        user_id: User ID whose portfolio to import into
        file_path: Absolute path to the saved upload file on disk
    """
    app = create_app()
    with app.app_context():
        task = BackgroundTask.query.get(task_id)
        if not task:
            logger.error(f"TASK {self.request.id}: BackgroundTask {task_id} not found")
            return json.dumps({"status": "failed", "message": "Task record not found"})

        try:
            task.status = 'running'
            task.started_at = now_utc()
            db.session.commit()

            logger.info(f"TASK {self.request.id}: Starting portfolio import for user {user_id} from {os.path.basename(file_path)}")

            importer = PortfolioImporter(user_id)
            result = importer.process_file_from_path(file_path)

            logger.info(f"TASK {self.request.id}: Import completed - {result['count']} transactions, {result['companies']} companies")

            task.status = 'completed'
            task.completed_at = now_utc()
            task.result = json.dumps({
                "count": result['count'],
                "skipped": result.get('skipped', 0),
                "companies": result['companies'],
                "date_range": result['date_range'],
                "message": result.get('message', f"Imported {result['count']} transactions for {result['companies']} companies")
            })
            db.session.commit()

            return json.dumps({"status": "success", "result": result})

        except (PortfolioImportError, ValueError) as e:
            logger.error(f"TASK {self.request.id}: Import error - {e}")
            task.status = 'failed'
            task.completed_at = now_utc()
            task.error_message = str(e)
            db.session.commit()
            return json.dumps({"status": "failed", "message": str(e)})

        except Exception as e:
            logger.error(f"TASK {self.request.id}: Unexpected error - {e}", exc_info=True)
            task.status = 'failed'
            task.completed_at = now_utc()
            task.error_message = str(e)
            db.session.commit()
            return json.dumps({"status": "failed", "message": str(e)})

        finally:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
                    logger.info(f"TASK {self.request.id}: Cleaned up temp file {file_path}")
            except OSError as cleanup_err:
                logger.warning(f"TASK {self.request.id}: Failed to clean up {file_path}: {cleanup_err}")
