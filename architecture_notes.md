  # Non-blocking celery task
    ┌─────────────────────────────────────────────────────────────────┐
  │                        DATABASE (Shared State)                  │
  │                                                                 │
  │  BackgroundTask Table:                                         │
  │  ┌──────────────────────────────────────────────────────────┐ │
  │  │ id (UUID)           | user_id | task_type | status        │ │
  │  │ result (JSON TEXT)  | error   | created_at | completed_at │ │
  │  └──────────────────────────────────────────────────────────┘ │
  │         ↑ WRITE (create)                  ↑ WRITE (update)    │
  │         │                                  │                   │
  │    ┌────┴─────┐                      ┌────┴─────┐            │
  │    │  FLASK   │                      │  CELERY  │            │
  │    │   APP    │                      │  WORKER  │            │
  │    └──────────┘                      └──────────┘            │
  └─────────────────────────────────────────────────────────────────┘
  
  Flask App (creates)          Celery Worker (updates)
       ↓                              ↓
  BackgroundTask DB Record ← shared → BackgroundTask DB Record

  Step-by-step:
  1. Flask creates BackgroundTask record: status='pending', result=NULL
  2. Flask passes task_id to Celery and returns immediately
  3. Celery fetches the same record: BackgroundTask.query.get(task_id)
  4. Celery updates: status='running', then status='completed', result='{"analysis": ...}'
  5. Flask polls the record to check status and retrieve results




