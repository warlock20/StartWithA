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
    add_suggested_criterion, default_kill_checklist, mistake_ids_with_criteria,
    undo_suggested_criterion,
)

SUGGESTION_STALL_SECONDS = 300


def _json_object():
    """The JSON request body if it is an object, else an empty dict."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _parse_id(value):
    """An int id from an int or an ASCII-digit string; None stays None; anything else raises ValueError."""
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    raise ValueError('invalid id')

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
    
    top_costly_mistakes = sorted(
        (m for m in mistakes if m.cost_estimate),
        key=lambda m: m.cost_estimate, reverse=True
    )[:3]
    top_reviewed_mistakes = sorted(
        (m for m in mistakes if (m.times_reviewed or 0) > 0),
        key=lambda m: m.times_reviewed, reverse=True
    )[:3]

    # Most common mistake type
    if by_type:
        most_common_type = max(by_type, key=lambda k: len(by_type[k]))
        most_common_count = len(by_type[most_common_type])
    else:
        most_common_type = None
        most_common_count = 0
    
    checklists = KillChecklist.query.filter_by(user_id=current_user.id).order_by(
        KillChecklist.is_default.desc(), KillChecklist.name, KillChecklist.id
    ).all()
    default_checklist = default_kill_checklist(current_user.id)
    kill_checklists = [
        {'id': c.id, 'name': c.name, 'criteria_count': c.criteria.count(), 'is_default': bool(c.is_default)}
        for c in checklists
    ]

    # Banner after logging a mistake: only for a mistake the user owns
    suggest_for = request.args.get('suggest_for', type=int)
    suggest_mistake = next((m for m in mistakes if m.id == suggest_for), None)

    return render_template('mistake_log.html',
                            title="Mistake Log",
                            kill_checklists=kill_checklists,
                            default_checklist_id=default_checklist.id if default_checklist else None,
                            mistakes_with_criteria=mistake_ids_with_criteria(current_user.id),
                            suggest_for=suggest_mistake.id if suggest_mistake else None,
                            suggest_mistake=suggest_mistake,
                            mistakes=mistakes,
                            top_costly_mistakes=top_costly_mistakes,
                            top_reviewed_mistakes=top_reviewed_mistakes,
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
    try:
        checklist_id = _parse_id(_json_object().get('checklist_id'))
    except ValueError:
        return jsonify({'error': 'checklist_id must be a number.'}), 400
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
    data = _json_object()
    try:
        checklist_id = _parse_id(data.get('checklist_id'))
    except ValueError:
        return jsonify({'error': 'checklist_id must be a number.'}), 400
    checklist = owned_or_404(KillChecklist, checklist_id)
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
    ordered_ids = [c.id for c in checklist.criteria.all()]
    return jsonify({
        'criterion_id': criterion.id,
        'order': criterion.order,
        'position': ordered_ids.index(criterion.id) + 1,
        'checklist_id': checklist.id,
        'checklist_name': checklist.name,
        'checklist_url': url_for('ideas.edit_kill_checklist', checklist_id=checklist.id),
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
