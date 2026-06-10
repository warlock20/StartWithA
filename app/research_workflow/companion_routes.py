# Investment Checklist Platform
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
Research Companion Routes

API endpoints for companion features:
- POST /companion/<project_id>/brief — generate research brief
- POST /companion/<project_id>/ask — live companion chat
- POST /companion/<project_id>/counter-evidence — counter-evidence for a finding
- POST /companion/<project_id>/wrapup — session wrap-up
- POST /companion/<project_id>/capture — quick-capture (creates JournalEntry)
"""

import logging
from flask import request
from flask_login import current_user, login_required

from app import db
from app.models.research import ResearchProject
from app.models.journal import JournalEntry
from app.research_workflow import research_workflow_bp
from app.services.argos import ArgosService
from app.utils.time_utils import now_utc
from app.utils.response_utils import json_success, json_error, json_validation_error
from app.utils.auth_utils import get_user_resource_or_403
from app.utils.db_utils import safe_commit, safe_add_and_commit

logger = logging.getLogger(__name__)


# =========================================================================
# Warnings (Zero Token Cost — DB Queries Only)
# =========================================================================

@research_workflow_bp.route('/companion/<int:project_id>/warnings', methods=['GET'])
@login_required
def companion_warnings(project_id):
    """Get proactive warnings for a project — pattern warnings + journal insights + mistakes.
    Pure DB queries, zero token cost. Auto-loaded on page load."""
    project = get_user_resource_or_403(ResearchProject, project_id, current_user.id)

    try:
        argos = ArgosService(user_id=current_user.id)
        warnings = argos.get_warnings(project_id)
        return json_success('Warnings loaded', data={'warnings': warnings})
    except Exception as e:
        logger.error(f"Warnings load failed: {e}")
        return json_error(str(e), status_code=500)


# =========================================================================
# Research Brief
# =========================================================================

@research_workflow_bp.route('/companion/<int:project_id>/brief', methods=['POST'])
@login_required
def companion_brief(project_id):
    """Generate a pre-session research brief."""
    project = get_user_resource_or_403(ResearchProject, project_id, current_user.id)
    step_index = request.json.get('step_index', project.current_step_index)

    try:
        argos = ArgosService(user_id=current_user.id)
        context = argos.build_research_context(project_id, step_index=step_index)
        brief = argos.generate_brief(context)
        return json_success('Brief generated', data={'brief': brief})
    except Exception as e:
        logger.error(f"Brief generation failed: {e}")
        return json_error(str(e), status_code=500)


# =========================================================================
# Live Companion Chat
# =========================================================================

@research_workflow_bp.route('/companion/<int:project_id>/ask', methods=['POST'])
@login_required
def companion_ask(project_id):
    """Ask the companion a question during research."""
    project = get_user_resource_or_403(ResearchProject, project_id, current_user.id)

    data = request.json or {}
    user_question = data.get('question', '').strip()
    conversation_history = data.get('conversation_history', [])
    step_index = data.get('step_index', project.current_step_index)

    if not user_question:
        return json_validation_error('Question is required')

    try:
        argos = ArgosService(user_id=current_user.id)
        context = argos.build_research_context(project_id, step_index=step_index)
        answer = argos.ask_companion(context, user_question, conversation_history)
        return json_success('Answer generated', data={'answer': answer})
    except Exception as e:
        logger.error(f"Companion chat failed: {e}")
        return json_error(str(e), status_code=500)


# =========================================================================
# Session Wrap-Up
# =========================================================================

@research_workflow_bp.route('/companion/<int:project_id>/wrapup', methods=['POST'])
@login_required
def companion_wrapup(project_id):
    """Generate a session wrap-up summary."""
    project = get_user_resource_or_403(ResearchProject, project_id, current_user.id)

    data = request.json or {}
    session_findings = data.get('session_findings', [])
    duration_minutes = data.get('duration_minutes', 0)
    counter_evidence = data.get('counter_evidence', [])
    step_index = data.get('step_index', project.current_step_index)

    try:
        argos = ArgosService(user_id=current_user.id)
        context = argos.build_research_context(project_id, step_index=step_index)
        wrapup = argos.wrap_up_session(context, session_findings, duration_minutes, counter_evidence)

        # Store in session_history
        if not project.session_history:
            project.session_history = []
        project.session_history = project.session_history + [{
            'step_index': step_index,
            'duration_minutes': duration_minutes,
            'summary': wrapup,
            'timestamp': now_utc().isoformat(),
        }]
        safe_commit(db.session, 'session wrap-up')

        return json_success('Session wrapped up', data={'wrapup': wrapup})
    except Exception as e:
        logger.error(f"Session wrap-up failed: {e}")
        return json_error(str(e), status_code=500)


# =========================================================================
# Quick Capture (Bookmarklet — uses JournalEntry)
# =========================================================================

@research_workflow_bp.route('/companion/<int:project_id>/capture', methods=['POST'])
@login_required
def companion_capture(project_id):
    """Capture a research finding from external source as a JournalEntry."""
    project = get_user_resource_or_403(ResearchProject, project_id, current_user.id)

    data = request.json or {}
    text = data.get('text', '').strip()
    url = data.get('url', '').strip() or None
    source_title = data.get('source_title', '').strip() or None

    if not text:
        return json_validation_error('Text is required')

    entry = JournalEntry(
        user_id=current_user.id,
        title=source_title or 'External capture',
        entry_type='observation',
        content=text,
        source=source_title,
        source_url=url,
        company_id=project.company_id,
        project_id=project_id,
        tags=['external_capture'],
        created_at=now_utc(),
    )

    success = safe_add_and_commit(db.session, entry, 'quick capture')
    if success:
        return json_success('Captured', data={'entry_id': entry.id})
    return json_error('Failed to save capture', status_code=500)
