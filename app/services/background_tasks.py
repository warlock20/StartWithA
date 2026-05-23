"""
Background task service for LLM operations
Uses Celery for robust task processing
"""

import uuid
import json
from datetime import datetime, timedelta
from app import db
from app.models import BackgroundTask
from app.utils.time_utils import now_utc
import logging
from app.celery_tasks import competitor_analysis_task
from app.celery_tasks import portfolio_ai_analysis_task
from app.celery_tasks import portfolio_chart_data_task
from app.celery_tasks import bias_check_task
from app.celery_tasks import argos_deep_analysis_task
from app.celery_tasks import portfolio_import_task
from app.celery_tasks import checklist_item_analyze_task
from app.celery_tasks import ai_research_assist_task

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
    def start_portfolio_import(user_id, file_path):
        """Start a portfolio import task in the background.

        Uses task_type 'portfolio_import' to prevent duplicate concurrent imports.
        """
        task_type = 'portfolio_import'

        existing_task = BackgroundTask.query.filter_by(
            user_id=user_id,
            task_type=task_type,
            status='running'
        ).first()

        if existing_task:
            logger.info(f"Import task {existing_task.id} already running for user {user_id}")
            return existing_task.id

        task_id = str(uuid.uuid4())
        task = BackgroundTask(
            id=task_id,
            user_id=user_id,
            task_type=task_type,
            status='pending'
        )

        db.session.add(task)
        db.session.commit()

        celery_task = portfolio_import_task.delay(task_id, user_id, file_path)

        logger.info(f"Started portfolio import task {task_id} (Celery: {celery_task.id}) for user {user_id}")

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

    @staticmethod
    def start_argos_deep_analysis(user_id, company_id, step_type, step_context, current_text, include_companion_warnings):
        """Start an Argos deep analysis task in the background.

        Uses task_type 'argos_deep_analysis' to prevent duplicate concurrent tasks.
        Company-level analysis (no project_id needed).
        """
        task_type = 'argos_deep_analysis'

        # Check for existing running task for this user
        existing_task = BackgroundTask.query.filter_by(
            user_id=user_id,
            task_type=task_type,
            status='running'
        ).first()

        if existing_task:
            logger.info(f"Argos deep analysis task {existing_task.id} already running for user {user_id}")
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
        celery_task = argos_deep_analysis_task.delay(
            task_id, user_id, company_id, step_type, step_context, current_text, include_companion_warnings
        )

        logger.info(f"Started argos deep analysis task {task_id} (Celery: {celery_task.id}) for user {user_id}")

        return task_id

    @staticmethod
    def start_checklist_item_analysis(user_id, analysis_id, item_id, selected_document_ids=None):
        """Start a checklist item AI analysis task (Run Prompt) in the background.

        Uses task_type 'checklist_item_analyze' to prevent duplicate concurrent tasks.
        """
        task_type = 'checklist_item_analyze'

        # Check for existing running task for the same item in the same session
        existing_task = BackgroundTask.query.filter_by(
            user_id=user_id,
            task_type=task_type,
            status='running'
        ).first()

        if existing_task:
            logger.info(f"Checklist item analysis task {existing_task.id} already running for user {user_id}")
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
        celery_task = checklist_item_analyze_task.delay(
            task_id, user_id, analysis_id, item_id, selected_document_ids or []
        )

        logger.info(f"Started checklist item analysis task {task_id} (Celery: {celery_task.id}) for item {item_id}")

        return task_id

    @staticmethod
    def start_ai_research_assist(user_id, mode, question_text, answer_text,
                                 company_name, use_google_search=False,
                                 analysis_id=None, item_id=None):
        """Start an AI Research Assistant task (Challenge/Elaboration/Fact-Check) in the background.

        Uses task_type 'ai_research_assist' to prevent duplicate concurrent tasks.
        """
        task_type = 'ai_research_assist'

        # Cancel any stale running/pending tasks for this user
        BackgroundTask.query.filter(
            BackgroundTask.user_id == user_id,
            BackgroundTask.task_type == task_type,
            BackgroundTask.status.in_(['running', 'pending']),
        ).update({'status': 'failed', 'error_message': 'Superseded by new request'}, synchronize_session='fetch')
        db.session.commit()

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
        celery_task = ai_research_assist_task.delay(
            task_id, user_id, mode, question_text, answer_text,
            company_name, use_google_search, analysis_id, item_id
        )

        logger.info(f"Started AI research assist task {task_id} (Celery: {celery_task.id}, mode: {mode}) for user {user_id}")

        return task_id