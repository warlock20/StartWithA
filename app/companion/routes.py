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
Global companion routes.

- POST /companion/ask       — agentic chat grounded in the user's whole account
- POST /companion/capture   — quick-capture an insight as a JournalEntry
- GET  /companion/warnings  — zero-token proactive warnings for a company

Focus is a page hint: {'type': 'company'|'research'|'portfolio', 'id': int, 'step': int}.
Every handler is scoped to current_user; the agent/executor enforce ownership below.
"""

import logging

from flask import request
from flask_login import current_user, login_required

from app import db
from app.companion import companion_bp
from app.models.journal import JournalEntry
from app.models.research import ResearchProject
from app.models.company import Company
from app.models.background_task import BackgroundTask
from app.services.argos import ArgosService
from app.services.argos.page_context import build_context_chips
from app.services.argos.selection_assist import find_evidence_for_selection
from app.services.argos.verbs import list_verbs
from app.services.background_tasks import BackgroundTaskService
from app.utils.time_utils import now_utc
from app.utils.response_utils import json_success, json_error, json_validation_error
from app.utils.db_utils import safe_add_and_commit

logger = logging.getLogger(__name__)


@companion_bp.app_context_processor
def inject_companion_context_chips():
    """Expose the rail's context chips to every template.

    Registered app-wide (``app_context_processor``) because _base.html renders the
    rail on every page, but kept here so the models it needs can be imported at
    module top rather than inside the factory.
    """
    def companion_context_chips(focus):
        if not current_user.is_authenticated:
            return []
        return build_context_chips(current_user.id, focus)

    return dict(companion_context_chips=companion_context_chips,
                companion_verbs=list_verbs)


def _capture_link(focus):
    """
    Resolve (company_id, project_id) a capture should attach to.

    A research project always belongs to a company, so a research capture links both;
    a company capture links only the company. Ids come from focus explicitly and are
    VALIDATED against the current user — an unowned or missing id links nothing rather
    than trusting client input. `type` is a UI hint only and isn't used here.
    """
    project_id = focus.get('project_id')
    if project_id:
        project = ResearchProject.query.filter_by(
            id=project_id, user_id=current_user.id).first()
        if project:
            return project.company_id, project.id  # company derived from the project
        return None, None

    company_id = focus.get('company_id')
    if company_id:
        company = Company.query.filter_by(
            id=company_id, user_id=current_user.id).first()
        return (company.id if company else None), None

    return None, None


@companion_bp.route('/ask', methods=['POST'])
@login_required
def ask():
    """Kick off the agentic companion in the background. Returns a task_id to poll.

    The agent runs a multi-hop tool-calling loop + local embedding, so it runs in a
    Celery worker (like every other AI op) rather than blocking the web request.
    """
    data = request.get_json(silent=True) or {}
    question = (data.get('question') or '').strip()
    if not question:
        return json_validation_error('Question is required')

    history = data.get('history') or []
    focus = data.get('focus') or {}

    try:
        task_id = BackgroundTaskService.start_companion_ask(
            current_user.id, question, history, focus)
        return json_success('Companion working', data={'task_id': task_id})
    except Exception as e:
        logger.error(f"Companion ask kickoff failed: {e}")
        return json_error(str(e), status_code=500)


@companion_bp.route('/ask/status/<task_id>', methods=['GET'])
@login_required
def ask_status(task_id):
    """Poll a companion task. Returns {status, result?/error?}. Ownership-checked."""
    task = BackgroundTask.query.filter_by(id=task_id, user_id=current_user.id).first()
    if not task:
        return json_error('Task not found', status_code=404)

    status = BackgroundTaskService.get_task_status(task_id)
    return json_success('Task status', data=status)


@companion_bp.route('/capture', methods=['POST'])
@login_required
def capture():
    """Capture a finding from an external source as a JournalEntry."""
    data = request.get_json(silent=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        return json_validation_error('Text is required')

    source_title = (data.get('source_title') or '').strip() or None
    url = (data.get('url') or '').strip() or None
    focus = data.get('focus') or {}
    company_id, project_id = _capture_link(focus)

    entry = JournalEntry(
        user_id=current_user.id,
        title=source_title or 'External capture',
        entry_type='observation',
        content=text,
        source=source_title,
        source_url=url,
        company_id=company_id,
        project_id=project_id,
        tags=['external_capture'],
        created_at=now_utc(),
    )
    if safe_add_and_commit(db.session, entry, 'companion capture'):
        return json_success('Captured', data={'entry_id': entry.id})
    return json_error('Failed to save capture', status_code=500)


@companion_bp.route('/selection', methods=['POST'])
@login_required
def selection():
    """Evidence from the user's own knowledge for a highlighted phrase.

    Retrieval only — no LLM, no tokens. Nobody asked a question here, so an empty
    list is a normal, common answer: the popover simply doesn't appear.

    `company_id` narrows the search when the page is focused on one; it's a hint,
    and retrieval is scoped to `current_user` regardless of what's sent.
    """
    data = request.get_json(silent=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        return json_validation_error('Selection is required')

    company_id = data.get('company_id')
    try:
        evidence = find_evidence_for_selection(
            current_user.id, text, company_id=company_id)
        return json_success('Evidence loaded', data={'evidence': evidence})
    except Exception as e:
        logger.error(f"Companion selection lookup failed: {e}")
        return json_error(str(e), status_code=500)


@companion_bp.route('/warnings', methods=['GET'])
@login_required
def warnings():
    """Proactive warnings for a company — pattern/journal/mistake history. Zero token cost."""
    company_id = request.args.get('company_id', type=int)
    if not company_id:
        return json_validation_error('company_id is required')

    try:
        argos = ArgosService(user_id=current_user.id)
        return json_success('Warnings loaded',
                            data={'warnings': argos.get_warnings_by_company(company_id)})
    except Exception as e:
        logger.error(f"Companion warnings failed: {e}")
        return json_error(str(e), status_code=500)
