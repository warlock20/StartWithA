from celery import Celery

# Create the Celery instance, but don't configure it with the app yet.
# The name 'app.celery' is a common convention.
celery = Celery('app.celery',
                # We can set the broker and backend here, or let the app config do it.
                # Let's let the app do it to keep things central.
                broker='redis://localhost:6379/0',
                backend='redis://localhost:6379/0',
                include=['app.tasks']
                )