"""
Celery Tasks Module

All Celery tasks organized by domain:
- tasks_portfolio: Portfolio AI analytics
- tasks_research: Competitor analysis, bias check, argos
- tasks_financial: Financial data, SEC filings
- tasks_data_retention: GDPR data retention / anonymization

Tasks are automatically discovered by Celery when this module is imported.
"""

# Import all tasks so Celery can discover them
from app.celery_tasks.tasks_portfolio import (
    portfolio_ai_analysis_task,
)

from app.celery_tasks.tasks_chart_data import (
    portfolio_chart_data_task,
)

from app.celery_tasks.tasks_research import (
    competitor_analysis_task,
    bias_check_task,
    argos_deep_analysis_task,
)

from app.celery_tasks.tasks_financial import (
    fetch_financial_data_task,
    fetch_sec_filings_task,
)

from app.celery_tasks.tasks_data_retention import (
    anonymize_ai_interactions,
)

from app.celery_tasks.tasks_import import (
    portfolio_import_task,
)

__all__ = [
    # Portfolio tasks
    'portfolio_ai_analysis_task',
    'portfolio_chart_data_task',
    'portfolio_import_task',

    # Research tasks
    'competitor_analysis_task',
    'bias_check_task',
    'argos_deep_analysis_task',

    # Financial tasks
    'fetch_financial_data_task',
    'fetch_sec_filings_task',

    # Data retention tasks
    'anonymize_ai_interactions',
]
