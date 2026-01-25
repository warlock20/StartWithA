---
name: background-task
description: Use when implementing background tasks for AI operations or long-running processes
---

# Background Task Implementation Guide

This skill guides the implementation of background tasks for AI operations in this platform. Background tasks prevent UI blocking and enable proper resource management.

## When to Use Background Tasks

- AI analysis that takes > 5 seconds
- Operations that consume tokens and should be tracked
- Tasks that users might trigger multiple times (need duplicate prevention)
- Operations where results should be cached for reuse

---

## Key Architecture

### Files
| File | Purpose |
|------|---------|
| `app/models/background_task.py` | BackgroundTask model |
| `app/services/background_tasks.py` | BackgroundTaskService (create, track, status) |
| `app/celery_tasks/tasks_*.py` | Celery task implementations |
| `app/models/user.py` | Token tracking (`can_use_ai_tokens`, `increment_ai_tokens`) |

### Task Type Format
Use **composite task_type** for grouping: `{category}:{template_name}`

Examples:
- `portfolio_analysis:behavioral`
- `portfolio_analysis:quick_overview`
- `bias_check:standard`
- `competitor_analysis`

This allows different analysis types to run concurrently while preventing duplicates of the same type.

---

## Implementation Checklist

### Step 1: Define Task Type Constant
```python
# In your routes or service file
TASK_TYPE = 'bias_check'  # or 'bias_check:{variant}' for multiple variants
ESTIMATED_TOKENS = 3000   # Estimate for token checking
```

### Step 2: Add Route with Duplicate Prevention + Token Check
```python
@blueprint.route('/api/your-task/<int:entity_id>', methods=['POST'])
@login_required
def start_your_task(entity_id):
    """Start background task with proper checks."""

    # 1. DUPLICATE PREVENTION - Check for running task
    existing_task = BackgroundTask.query.filter_by(
        user_id=current_user.id,
        task_type=TASK_TYPE,
        status='running'
    ).first()

    if existing_task:
        # Reuse existing task instead of creating new one
        return jsonify({
            'success': True,
            'task_id': existing_task.id,
            'message': 'Analysis already in progress'
        })

    # 2. TOKEN CHECK - Before expensive AI work
    if not current_user.can_use_ai_tokens(ESTIMATED_TOKENS):
        return jsonify({
            'success': False,
            'error': f'Token limit reached. Used {current_user.ai_tokens_used:,} of {current_user.ai_tokens_limit:,}'
        }), 429

    # 3. CREATE TASK RECORD
    task_id = BackgroundTaskService.start_task(
        user_id=current_user.id,
        task_type=TASK_TYPE,
        entity_id=entity_id  # project_id, company_id, etc.
    )

    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': 'Analysis started'
    })
```

### Step 3: Add Status Polling Endpoint
```python
@blueprint.route('/api/your-task/status/<task_id>')
@login_required
def get_task_status(task_id):
    """Poll task status for UI updates."""
    task = BackgroundTask.query.get(task_id)

    if not task or task.user_id != current_user.id:
        return jsonify({'state': 'NOT_FOUND'}), 404

    response = {
        'state': task.status.upper(),
        'current': {'pending': 10, 'running': 50, 'completed': 100, 'failed': 0}.get(task.status, 0),
        'total': 100
    }

    if task.status == 'completed' and task.result:
        response['result'] = json.loads(task.result)
    elif task.status == 'failed':
        response['error'] = task.error_message

    return jsonify(response)
```

### Step 4: Create Celery Task
```python
# app/celery_tasks/tasks_your_feature.py

from app.celery_app import celery
from app import create_app, db
from app.models import BackgroundTask, User
from app.utils.time_utils import now_utc

@celery.task(bind=True)
def your_analysis_task(self, task_id, user_id, entity_id):
    """
    Celery background task for your analysis.

    Args:
        task_id: BackgroundTask ID for status tracking
        user_id: User ID for token tracking
        entity_id: The entity to analyze (project_id, etc.)
    """
    app = create_app()
    with app.app_context():
        task = BackgroundTask.query.get(task_id)
        if not task:
            return {"status": "failed", "message": "Task not found"}

        try:
            # 1. UPDATE STATUS TO RUNNING
            task.status = 'running'
            task.started_at = now_utc()
            db.session.commit()

            # 2. DO THE WORK
            result, tokens_used = your_analysis_function(entity_id)

            # 3. TRACK TOKEN USAGE
            user = User.query.get(user_id)
            if user:
                user.increment_ai_tokens(tokens_used)

            # 4. SAVE RESULT
            task.status = 'completed'
            task.completed_at = now_utc()
            task.result = json.dumps({
                'analysis': result,
                'tokens_used': tokens_used
            })
            db.session.commit()

            return {"status": "success", "tokens_used": tokens_used}

        except Exception as e:
            # 5. HANDLE FAILURE
            task.status = 'failed'
            task.completed_at = now_utc()
            task.error_message = str(e)
            db.session.commit()

            return {"status": "failed", "message": str(e)}
```

### Step 5: Register Celery Task
```python
# app/celery_tasks/__init__.py
from .tasks_your_feature import your_analysis_task
```

### Step 6: Update BackgroundTaskService (if needed)
```python
# app/services/background_tasks.py

@staticmethod
def start_your_task(user_id, entity_id):
    """Start your analysis task in the background."""
    from app.celery_tasks.tasks_your_feature import your_analysis_task

    task_type = 'your_task_type'

    # Check for existing running task
    existing = BackgroundTask.query.filter_by(
        user_id=user_id,
        task_type=task_type,
        status='running'
    ).first()

    if existing:
        return existing.id

    # Create new task
    task_id = str(uuid.uuid4())
    task = BackgroundTask(
        id=task_id,
        user_id=user_id,
        task_type=task_type,
        status='pending'
    )
    db.session.add(task)
    db.session.commit()

    # Start Celery task
    your_analysis_task.delay(task_id, user_id, entity_id)

    return task_id
```

---

## UI Integration

### Loading State (JavaScript)
```javascript
const TaskPoller = {
    taskId: null,
    pollInterval: null,

    start(taskId, onComplete, onError) {
        this.taskId = taskId;
        this.pollInterval = setInterval(() => this.poll(onComplete, onError), 2000);
    },

    async poll(onComplete, onError) {
        const response = await fetch(`/api/your-task/status/${this.taskId}`);
        const data = await response.json();

        if (data.state === 'SUCCESS') {
            clearInterval(this.pollInterval);
            onComplete(data.result);
        } else if (data.state === 'FAILURE') {
            clearInterval(this.pollInterval);
            onError(data.error);
        }
        // PENDING/STARTED - continue polling
    },

    stop() {
        if (this.pollInterval) clearInterval(this.pollInterval);
    }
};
```

### Loading Template Pattern
```html
<!-- Show loading spinner while task runs -->
<div id="loadingState">
    <div class="spinner-border"></div>
    <p>Analyzing... This may take a moment.</p>
</div>

<!-- Results container (hidden initially) -->
<div id="resultsState" style="display: none;">
    <!-- Results rendered here -->
</div>

<script>
document.addEventListener('DOMContentLoaded', () => {
    const taskId = '{{ task_id }}';
    if (taskId) {
        TaskPoller.start(taskId,
            (result) => {
                document.getElementById('loadingState').style.display = 'none';
                document.getElementById('resultsState').style.display = 'block';
                renderResults(result);
            },
            (error) => {
                alert('Analysis failed: ' + error);
            }
        );
    }
});
</script>
```

---

## Token Management

### User Model Methods
```python
# Already implemented in app/models/user.py

user.can_use_ai_tokens(5000)      # Check if user has enough tokens
user.increment_ai_tokens(3500)     # Add to usage after task completes
user.ai_tokens_used                # Current usage
user.ai_tokens_limit               # Monthly limit (default: 10,000)
user.ai_tokens_reset_date          # Auto-resets every 30 days
```

### Token Limits by Subscription (future)
```python
TOKEN_LIMITS = {
    'free': 10_000,
    'pro': 100_000,
    'enterprise': 1_000_000
}
```

---

## Duplicate Prevention Pattern

**IMPORTANT:** Only check for `status='running'`, not `pending` or `completed`.

```python
# CORRECT - Allows retries after completion/failure
existing = BackgroundTask.query.filter_by(
    user_id=user_id,
    task_type=task_type,
    status='running'          # Only running tasks block new ones
).first()

# WRONG - Would block retries forever
existing = BackgroundTask.query.filter_by(
    user_id=user_id,
    task_type=task_type
).first()
```

---

## Caching Results

For expensive operations, cache the latest completed result:

```python
def get_cached_or_run(user_id, task_type, entity_id, force_refresh=False):
    """Get cached result or start new task."""

    # Check for running task first
    running = BackgroundTask.query.filter_by(
        user_id=user_id,
        task_type=task_type,
        status='running'
    ).first()

    if running:
        return {'status': 'running', 'task_id': running.id}

    # Check cache unless force refresh
    if not force_refresh:
        latest = BackgroundTask.query.filter_by(
            user_id=user_id,
            task_type=task_type,
            status='completed'
        ).order_by(BackgroundTask.completed_at.desc()).first()

        if latest and latest.result:
            return {'status': 'cached', 'result': json.loads(latest.result)}

    # Start new task
    task_id = start_task(user_id, task_type, entity_id)
    return {'status': 'started', 'task_id': task_id}
```

---

## Quick Reference

| Pattern | Code |
|---------|------|
| Check running task | `BackgroundTask.query.filter_by(user_id=id, task_type=type, status='running').first()` |
| Check tokens | `current_user.can_use_ai_tokens(5000)` |
| Increment tokens | `user.increment_ai_tokens(tokens_used)` |
| Start Celery task | `your_task.delay(task_id, user_id, entity_id)` |
| Task status | `pending` → `running` → `completed` / `failed` |
| Composite type | `f'{category}:{template}'` e.g., `portfolio_analysis:behavioral` |
