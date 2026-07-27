web: gunicorn run:app --workers 2 --threads 4 --worker-class gthread --timeout 120 --keep-alive 5 --preload
worker: celery -A celery_app worker --loglevel=info
release: flask db upgrade