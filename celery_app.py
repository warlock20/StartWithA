import os
from celery import Celery

# Get Redis URL from environment, fallback to localhost for development
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Create the Celery instance
celery = Celery('app.celery_tasks',
                broker=REDIS_URL,
                backend=REDIS_URL,
                include=[
                    'app.celery_tasks.tasks_portfolio',  # Portfolio AI analytics tasks
                    'app.celery_tasks.tasks_research',   # Research & competitor analysis tasks
                    'app.celery_tasks.tasks_financial',  # Financial data & SEC filings tasks
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
)