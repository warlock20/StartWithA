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
from app.celery_tasks import portfolio_chart_data_task
from app.celery_tasks import bias_check_task

logger = logging.getLogger(__name__)


def parse_task_type(task_type: str) -> tuple:
    """
    Parse composite task_type into (category, template).

    Args:
        task_type: Task type string (e.g., 'portfolio_analysis:portfolio_raw_trade_analysis')

    Returns:
        Tuple of (category, template). If no separator found, returns (task_type, None).

    Examples:
        >>> parse_task_type('portfolio_analysis:behavioral')
        ('portfolio_analysis', 'behavioral')

        >>> parse_task_type('simple_task')
        ('simple_task', None)
    """
    parts = task_type.split(':', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return task_type, None


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
        """Start a portfolio AI analysis task in the background

        Uses composite task_type format: 'portfolio_analysis:{template_name}'
        This allows different analysis types to run concurrently while preventing duplicates.
        """

        # Create composite task_type
        task_type_full = f'portfolio_analysis:{template_name}'

        # Check if a task with the same type is already running
        existing_task = BackgroundTask.query.filter_by(
            user_id=user_id,
            task_type=task_type_full,
            status='running'
        ).first()

        if existing_task:
            logger.info(f"Task {existing_task.id} already running for {template_name}, reusing it")
            return existing_task.id

        # Create new task record
        task_id = str(uuid.uuid4())
        task = BackgroundTask(
            id=task_id,
            user_id=user_id,
            task_type=task_type_full,  # Use composite format
            status='pending'
        )

        db.session.add(task)
        db.session.commit()

        # Start Celery task with task_id as first parameter
        celery_task = portfolio_ai_analysis_task.delay(task_id, user_id, template_name)

        logger.info(f"Started portfolio analysis task {task_id} (Celery: {celery_task.id}, template: {template_name}) for user {user_id}")

        return task_id

    @staticmethod
    def start_chart_data_task(user_id, time_periods=12):
        """Start a chart data computation task in the background.

        Uses composite task_type 'chart_data:{time_periods}'.
        No AI tokens consumed — purely data retrieval.
        """
        task_type = f'chart_data:{time_periods}'

        # Check for existing running task
        existing_task = BackgroundTask.query.filter_by(
            user_id=user_id,
            task_type=task_type,
            status='running'
        ).first()

        if existing_task:
            logger.info(f"Chart data task {existing_task.id} already running for {time_periods}M, reusing it")
            return existing_task.id

        # Create new task record
        task_id = str(uuid.uuid4())
        task = BackgroundTask(
            id=task_id,
            user_id=user_id,
            task_type=task_type,
            status='pending'
        )

        db.session.add(task)
        db.session.commit()

        # Start Celery task
        celery_task = portfolio_chart_data_task.delay(task_id, user_id, time_periods)

        logger.info(f"Started chart data task {task_id} (Celery: {celery_task.id}, periods: {time_periods}) for user {user_id}")

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

    @staticmethod
    def start_bias_check(user_id, project_id):
        """Start a cognitive bias check task in the background.

        Uses task_type 'bias_check' to prevent duplicate concurrent tasks.
        """
        task_type = 'bias_check'

        # Check for existing running task for this project
        existing_task = BackgroundTask.query.filter_by(
            user_id=user_id,
            task_type=task_type,
            project_id=project_id,
            status='running'
        ).first()

        if existing_task:
            logger.info(f"Bias check task {existing_task.id} already running for project {project_id}")
            return existing_task.id

        # Create new task record
        task_id = str(uuid.uuid4())
        task = BackgroundTask(
            id=task_id,
            user_id=user_id,
            task_type=task_type,
            project_id=project_id,
            status='pending'
        )

        db.session.add(task)
        db.session.commit()

        # Start Celery task
        celery_task = bias_check_task.delay(task_id, user_id, project_id)

        logger.info(f"Started bias check task {task_id} (Celery: {celery_task.id}) for project {project_id}")

        return task_id