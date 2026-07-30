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
Companion background task.

The companion agent runs a multi-hop tool-calling loop (several sequential LLM
calls) and lazy-loads a local embedding model, so it runs in a Celery worker —
not the web process — matching every other AI operation in the app.
"""

import json
import logging

from app import db, create_app
from app.models import BackgroundTask, User
from celery_app import celery

from app.services.argos.agent import CompanionAgent
from app.utils.time_utils import now_utc

logger = logging.getLogger(__name__)


@celery.task(bind=True)
def companion_ask_task(self, task_id, user_id, question, history, focus):
    """Run CompanionAgent.ask in the background, tracking status on BackgroundTask."""
    app = create_app()
    with app.app_context():
        task = BackgroundTask.query.get(task_id)
        if not task:
            logger.error(f"TASK {self.request.id}: companion task {task_id} not found")
            return {"status": "failed", "message": "Task not found"}

        try:
            task.status = 'running'
            task.started_at = now_utc()
            db.session.commit()

            result = CompanionAgent(user_id).ask(question, history, focus)

            user = User.query.get(user_id)
            if user:
                user.increment_ai_tokens(500)

            task.status = 'completed'
            task.completed_at = now_utc()
            task.result = json.dumps(result)
            db.session.commit()

            logger.info(f"TASK {self.request.id}: companion answer for user {user_id} "
                        f"({result.get('hops')} hop(s))")
            return {"status": "completed", **result}

        except Exception as e:
            logger.error(f"TASK {self.request.id}: companion ask failed - {e}", exc_info=True)
            task = BackgroundTask.query.get(task_id)
            if task:
                task.status = 'failed'
                task.completed_at = now_utc()
                task.error_message = str(e)
                db.session.commit()
            return {"status": "failed", "message": str(e)}
