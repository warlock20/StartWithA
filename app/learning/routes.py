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

from flask import render_template, request, jsonify, url_for
from flask_login import current_user, login_required
from app import db
from app.models import BackgroundTask, MistakeLog
from app.models.idea_pipeline import KillChecklist, KillCriterion
from app.learning import learning_bp
from app.utils.time_utils import now_utc
from app.utils.decorators import json_errors
from app.utils.auth_utils import owned_or_404
from app.services.background_tasks import BackgroundTaskService
from app.services.kill_criterion_suggester import (
    KILL_CRITERION_TOKEN_ESTIMATE, CriterionInUse, DuplicateCriterion,
    add_suggested_criterion, default_kill_checklist, undo_suggested_criterion,
)

SUGGESTION_STALL_SECONDS = 300

@learning_bp.route('/mistakes')
@login_required
def mistake_log():
    """View and manage mistake log"""
    mistakes = current_user.mistake_logs.order_by(
        MistakeLog.created_at.desc()
    ).all()
    
    # Categorize mistakes
    by_type = {}
    for mistake in mistakes:
        if mistake.mistake_type not in by_type:
            by_type[mistake.mistake_type] = []
        by_type[mistake.mistake_type].append(mistake)
   
   # Calculate total cost
    total_cost = sum(m.cost_estimate or 0 for m in mistakes)
    
    # Most common mistake type
    if by_type:
        most_common_type = max(by_type, key=lambda k: len(by_type[k]))
        most_common_count = len(by_type[most_common_type])
    else:
        most_common_type = None
        most_common_count = 0
    
    return render_template('mistake_log.html',
                            title="Mistake Log",
                            mistakes=mistakes,
                            by_type=by_type,
                            total_cost=total_cost,
                            most_common_type=most_common_type,
                            most_common_count=most_common_count)

@learning_bp.route('/mistakes/<int:mistake_id>/review', methods=['POST'])
@login_required
@json_errors
def review_mistake(mistake_id):
   """Mark a mistake as reviewed"""
   mistake = owned_or_404(MistakeLog, mistake_id)
   
   mistake.times_reviewed += 1
   mistake.last_reviewed = now_utc()
   
   # Check if similar mistake was prevented
   prevented = (request.get_json(silent=True) or {}).get('prevented_similar', False)
   if prevented:
       mistake.prevented_similar += 1
   
   db.session.commit()
   return jsonify({
       'success': True,
       'times_reviewed': mistake.times_reviewed,
       'prevented_similar': mistake.prevented_similar
   })


@learning_bp.route('/mistakes/<int:mistake_id>/suggest-criterion', methods=['POST'])
@login_required
@json_errors
def suggest_criterion(mistake_id):
    """Start an AI suggestion of a kill question that would have caught this mistake."""
    mistake = owned_or_404(MistakeLog, mistake_id)
    checklist_id = (request.get_json(silent=True) or {}).get('checklist_id')
    if checklist_id is not None:
        checklist = owned_or_404(KillChecklist, checklist_id)
    else:
        checklist = default_kill_checklist(current_user.id)
    if checklist is None:
        return jsonify({'error': 'no_checklist'}), 400

    if not current_user.can_use_ai_tokens(KILL_CRITERION_TOKEN_ESTIMATE):
        return jsonify({
            'error': f'This needs about {KILL_CRITERION_TOKEN_ESTIMATE:,} AI tokens; '
                     f'you have {current_user.get_tokens_remaining():,} left this month.'
        }), 429

    task_id = BackgroundTaskService.start_kill_criterion_suggestion(current_user.id, mistake.id, checklist.id)
    return jsonify({'task_id': task_id}), 202


@learning_bp.route('/mistakes/suggest-criterion/<task_id>')
@login_required
@json_errors
def suggest_criterion_status(task_id):
    """Poll a kill-criterion suggestion task."""
    owned_or_404(BackgroundTask, task_id)
    BackgroundTaskService.fail_if_stalled(task_id, current_user.id, SUGGESTION_STALL_SECONDS)
    task = owned_or_404(BackgroundTask, task_id)
    db.session.refresh(task)
    return jsonify(BackgroundTaskService.poll_payload(task, BackgroundTaskService.stored_result(task)))


@learning_bp.route('/mistakes/<int:mistake_id>/criteria', methods=['POST'])
@login_required
@json_errors
def add_mistake_criterion(mistake_id):
    """Add a suggested question to one of the user's kill checklists."""
    mistake = owned_or_404(MistakeLog, mistake_id)
    data = request.get_json(silent=True) or {}
    checklist = owned_or_404(KillChecklist, data.get('checklist_id'))
    question = str(data.get('question') or '').strip()
    if not question:
        return jsonify({'error': 'Question is required.'}), 400
    position = 'first' if data.get('position') == 'first' else 'last'

    try:
        criterion = add_suggested_criterion(
            mistake, checklist, question,
            help_text=str(data.get('help_text') or ''),
            failure_reason=str(data.get('failure_reason') or ''),
            position=position,
        )
    except DuplicateCriterion:
        return jsonify({'error': 'That question is already on this checklist.'}), 409
    return jsonify({
        'criterion_id': criterion.id,
        'order': criterion.order,
        'checklist_id': checklist.id,
        'checklist_name': checklist.name,
        'checklist_url': url_for('ideas.manage_kill_checklists'),
    }), 201


@learning_bp.route('/mistakes/<int:mistake_id>/criteria/<int:criterion_id>', methods=['DELETE'])
@login_required
@json_errors
def undo_mistake_criterion(mistake_id, criterion_id):
    """Undo an added criterion, unless a kill session has already used it."""
    mistake = owned_or_404(MistakeLog, mistake_id)
    criterion = (
        KillCriterion.query
        .join(KillChecklist, KillCriterion.kill_checklist_id == KillChecklist.id)
        .filter(KillCriterion.id == criterion_id, KillChecklist.user_id == current_user.id,
                KillCriterion.source_mistake_id == mistake.id)
        .first_or_404()
    )
    try:
        undo_suggested_criterion(mistake, criterion)
    except CriterionInUse:
        return jsonify({'error': 'This criterion has already been used in a kill session.'}), 409
    return '', 204
