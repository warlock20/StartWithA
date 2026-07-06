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
                    'app.celery_tasks.tasks_research',         # Research & competitor analysis tasks
                    'app.celery_tasks.tasks_financial',        # Financial data & SEC filings tasks
                    'app.celery_tasks.tasks_data_retention',   # GDPR data retention tasks
                    'app.celery_tasks.tasks_import',           # Portfolio import tasks
                    'app.celery_tasks.tasks_checkpoint_analysis',  # Daily checkpoint analysis
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
        'checkpoint-daily-analysis': {
            'task': 'app.celery_tasks.tasks_checkpoint_analysis.analyze_all_checkpoints',
            'schedule': crontab(hour=20, minute=0),  # Daily at 20:00 UTC (end of US market day)
        },
    },
)