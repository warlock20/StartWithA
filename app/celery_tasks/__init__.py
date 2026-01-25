"""
Celery Tasks Module

All Celery tasks organized by domain:
- tasks_portfolio: Portfolio AI analytics
- tasks_research: Competitor analysis, scuttlebutt, news
- tasks_financial: Financial data, SEC filings

Tasks are automatically discovered by Celery when this module is imported.
"""

# Import all tasks so Celery can discover them
from app.celery_tasks.tasks_portfolio import (
    portfolio_ai_analysis_task,
)

from app.celery_tasks.tasks_research import (
    competitor_analysis_task,
    fetch_company_news_task,
    analyze_scuttlebutt_task,
    bias_check_task,
)

from app.celery_tasks.tasks_financial import (
    fetch_financial_data_task,
    fetch_sec_filings_task,
)

__all__ = [
    # Portfolio tasks
    'portfolio_ai_analysis_task',

    # Research tasks
    'competitor_analysis_task',
    'fetch_company_news_task',
    'analyze_scuttlebutt_task',
    'bias_check_task',

    # Financial tasks
    'fetch_financial_data_task',
    'fetch_sec_filings_task',
]
