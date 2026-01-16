from celery import Celery

# Create the Celery instance, but don't configure it with the app yet.
# The name 'app.celery' is a common convention.
celery = Celery('app.celery_tasks',
                broker='redis://localhost:6379/0',
                backend='redis://localhost:6379/0',
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
    result_backend='redis://localhost:6379/0',
    broker_url='redis://localhost:6379/0',
)