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

import logging

from app.celery_tasks.base import background_task
from app.models import User
from app.services.argos.agent import CompanionAgent

logger = logging.getLogger(__name__)


@background_task()
def companion_ask_task(self, task, user_id, question, history, focus):
    """Run CompanionAgent.ask in the background, tracking status on BackgroundTask."""
    result = CompanionAgent(user_id).ask(question, history, focus)

    user = User.query.get(user_id)
    if user:
        user.increment_ai_tokens(500)

    logger.info(f"TASK {self.request.id}: companion answer for user {user_id} "
                f"({result.get('hops')} hop(s))")
    return result
