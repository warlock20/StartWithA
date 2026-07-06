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
Bias Check API Routes

Endpoints for cognitive bias analysis of investment theses.
Based on Charlie Munger's "Psychology of Human Misjudgment" framework.

Uses background tasks for non-blocking analysis.
"""

import json
import logging
from flask import jsonify, request
from flask_login import current_user, login_required

from app import db, limiter
from app.research_workflow import research_workflow_bp
from app.constants import RATELIMIT_AI
from app.models import ResearchProject, BiasCheckResult, BackgroundTask
from app.services.background_tasks import BackgroundTaskService
from app.services.research_data_service import ResearchDataService
from app.utils.response_utils import json_success, json_error, json_unauthorized

logger = logging.getLogger(__name__)

# Minimum word count for meaningful analysis
MIN_WORD_COUNT = 200

# Token estimate for pre-check
ESTIMATED_TOKENS = 3000


@research_workflow_bp.route('/api/bias-check/<int:project_id>', methods=['POST'])
@login_required
@limiter.limit(RATELIMIT_AI)
def run_bias_check(project_id):
    """
    Start cognitive bias analysis on a project's research.

    Uses background task to prevent UI blocking.
    Returns task_id for polling.
    """
    # Get project
    project = ResearchProject.query.get_or_404(project_id)

    # Verify ownership
    if project.user_id != current_user.id:
        return json_unauthorized('Unauthorized')

    # 1. DUPLICATE PREVENTION - Check for running task
    existing_task = BackgroundTask.query.filter_by(
        user_id=current_user.id,
        task_type='bias_check',
        project_id=project_id,
        status='running'
    ).first()

    if existing_task:
        return jsonify({
            'success': True,
            'task_id': existing_task.id,
            'message': 'Analysis already in progress'
        })

    # 2. PRE-CHECK - Validate minimum word count before starting expensive task
    try:
        thesis_text = ResearchDataService.get_all_text(project, include_metadata=False)
        word_count = len(thesis_text.split())

        if word_count < MIN_WORD_COUNT:
            return jsonify({
                'success': False,
                'error': f'Insufficient research text. Found {word_count} words, minimum is {MIN_WORD_COUNT}.',
                'word_count': word_count,
                'min_required': MIN_WORD_COUNT
            }), 400
    except Exception as e:
        logger.error(f"Failed to gather research text for project {project_id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to gather research text'
        }), 500

    # 3. TOKEN CHECK - Before expensive AI work
    if not current_user.can_use_ai_tokens(ESTIMATED_TOKENS):
        return jsonify({
            'success': False,
            'error': f'Token limit reached. Used {current_user.ai_tokens_used:,} of {current_user.ai_tokens_limit:,}'
        }), 429

    # 4. START BACKGROUND TASK
    task_id = BackgroundTaskService.start_bias_check(
        user_id=current_user.id,
        project_id=project_id
    )

    logger.info(f"Started bias check task {task_id} for project {project_id}")

    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': 'Bias check started'
    })


@research_workflow_bp.route('/api/bias-check/status/<task_id>')
@login_required
def get_bias_check_status(task_id):
    """
    Poll task status for UI updates.

    Returns:
        JSON with state and result when completed
    """
    task = BackgroundTask.query.get(task_id)

    if not task or task.user_id != current_user.id:
        return jsonify({'state': 'NOT_FOUND'}), 404

    response = {
        'state': task.status.upper(),
        'current': {'pending': 10, 'running': 50, 'completed': 100, 'failed': 0}.get(task.status, 0),
        'total': 100
    }

    if task.status == 'completed' and task.result:
        task_result = json.loads(task.result)
        result_id = task_result.get('result_id')

        # Fetch the full bias check result
        if result_id:
            bias_result = BiasCheckResult.query.get(result_id)
            if bias_result:
                response['result'] = bias_result.to_dict()
                response['result_id'] = result_id

    elif task.status == 'failed':
        response['error'] = task.error_message or 'Analysis failed'

    return jsonify(response)


@research_workflow_bp.route('/api/bias-check/<int:project_id>/latest', methods=['GET'])
@login_required
def get_latest_bias_check(project_id):
    """
    Get the most recent bias check result for a project.

    Returns:
        JSON with latest bias check result or null if none exists
    """
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return json_unauthorized('Unauthorized')

    result = BiasCheckResult.get_latest_for_project(project_id)

    return jsonify({
        'success': True,
        'result': result.to_dict() if result else None,
        'has_result': result is not None
    })


@research_workflow_bp.route('/api/bias-check/result/<int:result_id>/feedback', methods=['POST'])
@login_required
def submit_bias_check_feedback(result_id):
    """
    Submit feedback for a bias check result.

    Request JSON:
        {"feedback": "helpful" | "not_helpful"}

    Returns:
        JSON success response
    """
    result = BiasCheckResult.query.get_or_404(result_id)

    if result.user_id != current_user.id:
        return json_unauthorized('Unauthorized')

    data = request.get_json() or {}
    feedback = data.get('feedback')

    if feedback not in ('helpful', 'not_helpful'):
        return jsonify({
            'success': False,
            'error': 'feedback must be "helpful" or "not_helpful"'
        }), 400

    if feedback == 'helpful':
        result.mark_helpful()
    else:
        result.mark_not_helpful()

    db.session.commit()

    logger.info(f"Bias check feedback: user={current_user.id}, result={result_id}, feedback={feedback}")

    return json_success()


@research_workflow_bp.route('/api/bias-check/user-patterns', methods=['GET'])
@login_required
def get_user_bias_patterns():
    """
    Get recurring bias patterns for the current user.

    Returns aggregated data about which biases appear most frequently
    in the user's research.

    Returns:
        JSON with bias pattern statistics
    """
    patterns = BiasCheckResult.get_user_bias_patterns(current_user.id)
    avg_score = BiasCheckResult.get_user_average_score(current_user.id)

    return jsonify({
        'success': True,
        'patterns': patterns,
        'average_score': avg_score,
        'total_checks': BiasCheckResult.query.filter_by(user_id=current_user.id).count()
    })


@research_workflow_bp.route('/api/bias-check/<int:project_id>/preview', methods=['GET'])
@login_required
def preview_bias_check_data(project_id):
    """
    Preview the data that will be used for bias check.

    Useful for debugging and showing users what text will be analyzed.

    Returns:
        JSON with research stats and word count
    """
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return json_unauthorized('Unauthorized')

    stats = ResearchDataService.get_research_stats(project)

    return jsonify({
        'success': True,
        'stats': stats,
        'can_run_check': stats['word_count'] >= MIN_WORD_COUNT,
        'min_word_count': MIN_WORD_COUNT
    })
