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
Celery Tasks Module

All Celery tasks organized by domain:
- tasks_portfolio: Portfolio AI analytics
- tasks_research: Competitor analysis, bias check, argos
- tasks_financial: Financial data, SEC filings
- tasks_data_retention: GDPR data retention / anonymization
- tasks_checkpoint_analysis: Daily checkpoint AI analysis

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
    checklist_item_analyze_task,
    ai_research_assist_task,
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

from app.celery_tasks.tasks_checkpoint_analysis import (
    analyze_all_checkpoints,
)

from app.celery_tasks.tasks_screening import (
    screening_analysis_task,
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
    'checklist_item_analyze_task',
    'ai_research_assist_task',

    # Financial tasks
    'fetch_financial_data_task',
    'fetch_sec_filings_task',

    # Data retention tasks
    'anonymize_ai_interactions',

    # Checkpoint analysis tasks
    'analyze_all_checkpoints',

    # Screening analysis tasks
    'screening_analysis_task',
]
