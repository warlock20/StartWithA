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

"""JSON API for the AI check island on the research step."""

import logging

from flask import jsonify, request
from flask_login import current_user, login_required

from app.celery_tasks.tasks_ai_check import (
    ai_check_analyze_task, ai_check_gather_task, claude_available, dispatch_extract_and_analyze,
)
from app.models import AICheckRun, ChecklistAnalysis, ChecklistItem
from app.research_workflow import research_workflow_bp
from app.services.ai_check import AICheckError
from app.services.ai_check.pipeline import (
    cancel_run, mark_failed, retry_run, serialize_history, serialize_run, start_run,
)
from app.utils.response_utils import json_error, json_unauthorized

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 10


def _session_and_item(analysis_id, item_id):
    session = ChecklistAnalysis.query.get_or_404(analysis_id)
    if session.researcher != current_user:
        return None, None, json_unauthorized('Unauthorized')
    item = ChecklistItem.query.get_or_404(item_id)
    if item.checklist_id != session.checklist_id:
        return None, None, json_error('Invalid item for this session.')
    return session, item, None


def _own_run(run_id):
    run = AICheckRun.query.get_or_404(run_id)
    if run.user_id != current_user.id:
        return None, json_unauthorized('Unauthorized')
    return run, None


@research_workflow_bp.route('/checklist/<int:analysis_id>/item/<int:item_id>/ai_check', methods=['POST'])
@login_required
def start_ai_check(analysis_id, item_id):
    session, item, error = _session_and_item(analysis_id, item_id)
    if error:
        return error
    if not claude_available():
        return json_error('Claude is not configured on the server.', status_code=503)
    data = request.get_json(silent=True) or {}
    try:
        run, created = start_run(current_user.id, session, item, data.get('mode'), data.get('document_ids'))
    except AICheckError as exc:
        return json_error(str(exc))
    if created:
        try:
            ai_check_gather_task.delay(run.id)
        except Exception as exc:
            logger.exception('Could not queue AI check gather for run %s', run.id)
            mark_failed(run, 'gathering', f'Could not queue the AI check: {exc}')
            return json_error('Could not queue the AI check. Try again in a moment.', status_code=503)
    return jsonify({'success': True, 'run': serialize_run(run)})


@research_workflow_bp.route('/checklist/<int:analysis_id>/item/<int:item_id>/ai_check/history')
@login_required
def ai_check_history(analysis_id, item_id):
    session, item, error = _session_and_item(analysis_id, item_id)
    if error:
        return error
    runs = AICheckRun.query.filter_by(
        user_id=current_user.id, company_id=session.company_id, checklist_item_id=item.id,
    ).order_by(AICheckRun.id.desc()).limit(HISTORY_LIMIT).all()
    return jsonify({'success': True, 'runs': serialize_history(runs),
                    'latest': serialize_run(runs[0]) if runs else None})


@research_workflow_bp.route('/ai_check/<int:run_id>')
@login_required
def ai_check_status(run_id):
    run, error = _own_run(run_id)
    if error:
        return error
    return jsonify({'success': True, 'run': serialize_run(run)})


@research_workflow_bp.route('/ai_check/<int:run_id>/cancel', methods=['POST'])
@login_required
def cancel_ai_check(run_id):
    run, error = _own_run(run_id)
    if error:
        return error
    cancel_run(run)
    return jsonify({'success': True, 'run': serialize_run(run)})


@research_workflow_bp.route('/ai_check/<int:run_id>/retry', methods=['POST'])
@login_required
def retry_ai_check(run_id):
    run, error = _own_run(run_id)
    if error:
        return error
    try:
        stage, source_ids = retry_run(run)
    except AICheckError as exc:
        return json_error(str(exc))
    try:
        if stage == 'gathering':
            ai_check_gather_task.delay(run.id)
        elif stage == 'extracting' and source_ids:
            dispatch_extract_and_analyze(run.id, source_ids)
        else:
            ai_check_analyze_task.delay(None, run.id)
    except Exception as exc:
        logger.exception('Could not queue AI check retry for run %s', run.id)
        mark_failed(run, stage, f'Could not queue the AI check: {exc}')
        return json_error('Could not queue the AI check. Try again in a moment.', status_code=503)
    return jsonify({'success': True, 'run': serialize_run(run)})
