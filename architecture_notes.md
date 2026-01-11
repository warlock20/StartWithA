  # Non-blocking celery task
  
  Flask App (creates)          Celery Worker (updates)
       ↓                              ↓
  BackgroundTask DB Record ← shared → BackgroundTask DB Record

  Flow:
  1. Flask creates a BackgroundTask record in the database with status='pending'
  2. Flask passes the task_id to Celery and returns immediately (non-blocking)
  3. Celery worker retrieves the same BackgroundTask record using task_id
  4. Celery updates the record: status='running', then status='completed' with results
  5. Flask (via polling) reads the updated record from the database