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

import os
from celery import Celery
from celery.schedules import crontab

# Get Redis URL from environment, fallback to localhost for development
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Create the Celery instance
celery = Celery('app.celery_tasks',
                broker=REDIS_URL,
                backend=REDIS_URL,
                include=[
                    'app.celery_tasks.tasks_portfolio',        # Portfolio AI analytics tasks
                    'app.celery_tasks.tasks_chart_data',       # Portfolio chart data tasks
                    'app.celery_tasks.tasks_research',         # Bias check, Argos and AI assist tasks
                    'app.celery_tasks.tasks_financial',        # Financial data & SEC filings tasks
                    'app.celery_tasks.tasks_data_retention',   # GDPR data retention tasks
                    'app.celery_tasks.tasks_import',           # Portfolio import tasks
                    'app.celery_tasks.tasks_monitors',              # Per-user background monitor runs
                    'app.celery_tasks.tasks_monitor_dispatch',      # Hourly dispatcher for monitor runs
                    'app.celery_tasks.tasks_screening',             # Screening analysis tasks
                    'app.celery_tasks.tasks_companion',             # Companion agentic chat tasks
                    'app.celery_tasks.tasks_ai_check',              # AI check pipeline
                    'app.celery_tasks.tasks_knowledge',             # Companion knowledge index
                    'app.celery_tasks.tasks_documents',             # Checklist import from uploaded documents
                    'app.celery_tasks.tasks_kill_criteria',         # Suggest a kill criterion from a mistake
                    'app.celery_tasks.tasks_watchlist',             # Watchlist valuation target check
                ]
                )

# Configure Celery
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    result_backend=REDIS_URL,
    broker_url=REDIS_URL,
    beat_schedule={
        'gdpr-anonymize-ai-interactions': {
            'task': 'app.celery_tasks.tasks_data_retention.anonymize_ai_interactions',
            'schedule': crontab(hour=3, minute=0),  # Daily at 03:00 UTC
        },
        'watchlist-target-check': {
            'task': 'app.celery_tasks.tasks_watchlist.check_watchlist_targets',
            'schedule': crontab(hour=21, minute=30),  # Daily at 21:30 UTC (after the US close in EST too)
        },
        'dispatch-user-monitors': {
            'task': 'app.celery_tasks.tasks_monitor_dispatch.dispatch_user_monitors',
            'schedule': crontab(minute=0),  # Hourly, on the hour
        },
        'ai-check-reap-stale-runs': {
            'task': 'app.celery_tasks.tasks_ai_check.ai_check_reap_task',
            'schedule': crontab(minute='*/10'),
        },
        'knowledge-index-nightly': {
            'task': 'app.celery_tasks.tasks_knowledge.index_all_knowledge',
            'schedule': crontab(hour=2, minute=0),  # Daily at 02:00 UTC
        },
        'prune-scheduled-job-runs': {
            'task': 'app.celery_tasks.tasks_data_retention.prune_scheduled_job_runs',
            'schedule': crontab(hour=3, minute=30),  # Daily at 03:30 UTC
        },
    },
)