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
Suggest-kill-criterion Celery task.

Asks the AI for a kill checklist question that would have caught a logged
mistake. The result is stored on the BackgroundTask row; nothing is added to a
checklist until the user presses Add.
"""

from app import db
from app.celery_tasks.base import TaskFailed, background_task
from app.models import User
from app.models.idea_pipeline import KillChecklist, MistakeLog
from app.services.kill_criterion_suggester import NoUsableSuggestion, suggest_kill_criteria


@background_task(soft_time_limit=120)
def suggest_kill_criterion_task(self, task, user_id, mistake_id, checklist_id):
    """Suggest 1-3 kill questions for a mistake and charge the AI tokens used."""
    mistake = MistakeLog.query.filter_by(id=mistake_id, user_id=user_id).first()
    checklist = KillChecklist.query.filter_by(id=checklist_id, user_id=user_id).first()
    if not mistake or not checklist:
        raise TaskFailed('This mistake or checklist no longer exists.')

    try:
        result = suggest_kill_criteria(mistake, checklist)
    except NoUsableSuggestion:
        raise TaskFailed("Couldn't get a usable suggestion. Please try again.")

    user = db.session.get(User, user_id)
    if user:
        user.increment_ai_tokens(result['tokens_used'])
    return result
