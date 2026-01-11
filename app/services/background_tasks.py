"""
Background task service for LLM operations
Uses Celery for robust task processing
"""

import uuid
import json
from datetime import timedelta
from app import db
from app.models import BackgroundTask
from app.utils.time_utils import now_utc
import logging
from app.celery_tasks import competitor_analysis_task
from app.celery_tasks import portfolio_ai_analysis_task

logger = logging.getLogger(__name__)


class BackgroundTaskService:
    @staticmethod
    def start_competitor_analysis(user_id, project_id, step_index, company):
        """Start a competitor analysis task in the background"""

        # Create task record
        task_id = str(uuid.uuid4())
        task = BackgroundTask(
            id=task_id,
            user_id=user_id,
            task_type='competitor_analysis',
            project_id=project_id,
            step_index=step_index,
            status='pending'
        )

        db.session.add(task)
        db.session.commit()

        # Extract company data for thread (avoid session issues)
        company_data = {
            'id': company.id,
            'name': company.name,
            'ticker_symbol': company.ticker_symbol,
            'summary': company.summary,
            'sector': company.sector,
            'industry': company.industry
        }

        # Start Celery task
        celery_task = competitor_analysis_task.delay(task_id, company_data)

        # Store Celery task ID for monitoring
        task.result = celery_task.id
        db.session.commit()

        return task_id

    @staticmethod
    def get_task_status(task_id):
        """Get current status of a background task"""
        task = BackgroundTask.query.get(task_id)
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
    def start_portfolio_analysis(user_id, template_name):
        """Start a portfolio AI analysis task in the background"""
        
        # Create task record
        task_id = str(uuid.uuid4())
        task = BackgroundTask(
            id=task_id,
            user_id=user_id,
            task_type='portfolio_analysis',
            status='pending'
        )

        db.session.add(task)
        db.session.commit()

        # Start Celery task with task_id as first parameter
        celery_task = portfolio_ai_analysis_task.delay(task_id, user_id, template_name)

        logger.info(f"Started portfolio analysis task {task_id} (Celery: {celery_task.id}, template: {template_name}) for user {user_id}")

        return task_id

    @staticmethod
    def cleanup_old_tasks(days_old=7):
        """Clean up completed/failed tasks older than X days"""
        cutoff_date = now_utc() - timedelta(days=days_old)

        old_tasks = BackgroundTask.query.filter(
            BackgroundTask.status.in_(['completed', 'failed']),
            BackgroundTask.completed_at < cutoff_date
        ).all()

        for task in old_tasks:
            db.session.delete(task)

        db.session.commit()
        logger.info(f"Cleaned up {len(old_tasks)} old background tasks")