"""
AI Research Assistant Routes

Flask routes for AI-powered research assistance:
- Dispatch AI challenges, elaborations, and fact-checks as background tasks
- Poll task status for async results
- Store user feedback for quality monitoring
- AJAX-based (no page reloads)

Routes:
- POST /research/ai_assist - Dispatch AI response task (returns task_id)
- GET  /research/ai_assist/status/<task_id> - Poll task status
- POST /research/ai_assist/feedback - Store user feedback
- POST /research/ai_assist/regenerate - Regenerate AI response (returns task_id)
"""

import logging
from flask import jsonify, request
from flask_login import current_user, login_required

from app import db
from app.research_workflow import research_workflow_bp
from app.models import ChecklistAnalysis, AIResearchFeedback
from app.services.background_tasks import BackgroundTaskService
from app.utils.decorators import require_ai_tokens

logger = logging.getLogger(__name__)

VALID_MODES = ['challenge', 'elaboration', 'factcheck']


@research_workflow_bp.route('/ai_assist', methods=['POST'])
@login_required
@require_ai_tokens(5000)
def ai_assist():
    """
    Dispatch AI research assistance as a background task.

    Request Body (JSON):
    {
        "mode": "challenge" | "elaboration" | "factcheck",
        "question_text": "What is the company's moat?",
        "answer_text": "Network effects from 2-sided marketplace",
        "analysis_id": 123,  // Optional - for context tracking
        "item_id": 456       // Optional - for context tracking
    }

    Response (JSON):
    {
        "success": true,
        "task_id": "uuid-string"
    }
    """
    try:
        # Parse request data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body must be JSON'
            }), 400

        # Extract required parameters
        mode = data.get('mode')
        question_text = data.get('question_text')
        answer_text = data.get('answer_text')

        # Validate required fields
        if not mode:
            return jsonify({
                'success': False,
                'error': 'mode is required (challenge, elaboration, or factcheck)'
            }), 400

        if mode not in VALID_MODES:
            return jsonify({
                'success': False,
                'error': f"Invalid mode '{mode}'. Valid modes: challenge, elaboration, factcheck"
            }), 400

        if not question_text or not question_text.strip():
            return jsonify({
                'success': False,
                'error': 'question_text is required'
            }), 400

        if not answer_text or not answer_text.strip():
            return jsonify({
                'success': False,
                'error': 'answer_text is required'
            }), 400

        # Extract optional context
        analysis_id = data.get('analysis_id')
        item_id = data.get('item_id')
        use_google_search = bool(data.get('use_google_search', False))

        # Get company name from context
        company_name = None
        if analysis_id:
            analysis = ChecklistAnalysis.query.filter_by(
                id=analysis_id,
                user_id=current_user.id  # Authorization check
            ).first()

            if analysis:
                company_name = analysis.company.name
            else:
                return jsonify({
                    'success': False,
                    'error': 'Invalid or unauthorized analysis_id'
                }), 403

        # If no analysis context, require company_name in request
        if not company_name:
            company_name = data.get('company_name', 'Unknown Company')

        # Dispatch background task
        logger.info(
            f"AI assist dispatch: user={current_user.id}, mode={mode}, "
            f"analysis={analysis_id}, item={item_id}, company={company_name}"
        )

        task_id = BackgroundTaskService.start_ai_research_assist(
            user_id=current_user.id,
            mode=mode,
            question_text=question_text,
            answer_text=answer_text,
            company_name=company_name,
            use_google_search=use_google_search,
            analysis_id=analysis_id,
            item_id=item_id
        )

        return jsonify({
            'success': True,
            'task_id': task_id
        }), 200

    except Exception as e:
        logger.error(f"Unexpected error in AI assist dispatch: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred. Please try again.'
        }), 500


@research_workflow_bp.route('/ai_assist/status/<task_id>')
@login_required
def ai_assist_status(task_id):
    """
    Poll status of an AI research assist background task.

    Response (JSON):
    {
        "state": "PENDING" | "RUNNING" | "COMPLETED" | "FAILED",
        "current": 0-100,
        "total": 100,
        // On COMPLETED:
        "response": "AI generated text...",
        "mode": "challenge",
        "tokens_used": 245,
        "feedback_id": 789
    }
    """
    task_status = BackgroundTaskService.get_task_status(task_id)

    if not task_status:
        return jsonify({'state': 'NOT_FOUND'}), 404

    response = {'current': 0, 'total': 100}

    if task_status['status'] == 'pending':
        response['state'] = 'PENDING'
        response['current'] = 10
    elif task_status['status'] == 'running':
        response['state'] = 'RUNNING'
        response['current'] = 50
    elif task_status['status'] == 'completed':
        response['state'] = 'COMPLETED'
        response['current'] = 100
        result = task_status.get('result', {})
        response['response'] = result.get('response', '')
        response['mode'] = result.get('mode', '')
        response['tokens_used'] = result.get('tokens_used', 0)
        response['feedback_id'] = result.get('feedback_id')
    elif task_status['status'] == 'failed':
        response['state'] = 'FAILED'
        response['error'] = task_status.get('error', 'AI analysis failed')

    return jsonify(response)


@research_workflow_bp.route('/ai_assist/feedback', methods=['POST'])
@login_required
def ai_assist_feedback():
    """
    Store user feedback for AI research assistance.

    Request Body (JSON):
    {
        "feedback_id": 789,
        "feedback": "helpful" | "not_helpful" | "dismissed"
    }

    Response (JSON):
    {
        "success": true,
        "message": "Feedback recorded"
    }

    Or on error:
    {
        "success": false,
        "error": "Invalid feedback_id"
    }
    """
    try:
        # Parse request data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body must be JSON'
            }), 400

        # Extract parameters
        feedback_id = data.get('feedback_id')
        feedback_value = data.get('feedback')

        # Validate required fields
        if not feedback_id:
            return jsonify({
                'success': False,
                'error': 'feedback_id is required'
            }), 400

        if not feedback_value:
            return jsonify({
                'success': False,
                'error': 'feedback is required (helpful, not_helpful, or dismissed)'
            }), 400

        # Validate feedback value
        valid_feedback = ['helpful', 'not_helpful', 'dismissed']
        if feedback_value not in valid_feedback:
            return jsonify({
                'success': False,
                'error': f"Invalid feedback '{feedback_value}'. Valid values: {valid_feedback}"
            }), 400

        # Find feedback record (with authorization check)
        feedback_record = AIResearchFeedback.query.filter_by(
            id=feedback_id,
            user_id=current_user.id  # Ensure user owns this record
        ).first()

        if not feedback_record:
            return jsonify({
                'success': False,
                'error': 'Invalid or unauthorized feedback_id'
            }), 404

        # Update feedback
        if feedback_value == 'helpful':
            feedback_record.mark_helpful()
        elif feedback_value == 'not_helpful':
            feedback_record.mark_not_helpful()
        elif feedback_value == 'dismissed':
            feedback_record.mark_dismissed()

        db.session.commit()

        logger.info(
            f"Feedback recorded: id={feedback_id}, user={current_user.id}, "
            f"mode={feedback_record.mode}, feedback={feedback_value}"
        )

        return jsonify({
            'success': True,
            'message': 'Feedback recorded',
            'feedback_id': feedback_id,
            'feedback': feedback_value
        }), 200

    except Exception as e:
        logger.error(f"Unexpected error recording feedback: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred. Please try again.'
        }), 500


@research_workflow_bp.route('/ai_assist/regenerate', methods=['POST'])
@login_required
@require_ai_tokens(5000)
def ai_assist_regenerate():
    """
    Regenerate AI response for the same question/answer as a background task.

    Request Body (JSON):
    {
        "feedback_id": 789
    }

    Response (JSON):
    {
        "success": true,
        "task_id": "uuid-string"
    }
    """
    try:
        # Parse request data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body must be JSON'
            }), 400

        feedback_id = data.get('feedback_id')
        use_google_search = bool(data.get('use_google_search', False))

        if not feedback_id:
            return jsonify({
                'success': False,
                'error': 'feedback_id is required'
            }), 400

        # Find original feedback record
        original_record = AIResearchFeedback.query.filter_by(
            id=feedback_id,
            user_id=current_user.id
        ).first()

        if not original_record:
            return jsonify({
                'success': False,
                'error': 'Invalid or unauthorized feedback_id'
            }), 404

        if original_record.mode not in VALID_MODES:
            return jsonify({
                'success': False,
                'error': f"Invalid mode '{original_record.mode}'"
            }), 400

        # Dispatch background task with original parameters
        task_id = BackgroundTaskService.start_ai_research_assist(
            user_id=current_user.id,
            mode=original_record.mode,
            question_text=original_record.question_text,
            answer_text=original_record.user_answer,
            company_name=original_record.company_name or 'Unknown Company',
            use_google_search=use_google_search,
            analysis_id=original_record.analysis_id,
            item_id=original_record.item_id
        )

        logger.info(
            f"AI response regeneration dispatched: original_id={feedback_id}, "
            f"task_id={task_id}, mode={original_record.mode}"
        )

        return jsonify({
            'success': True,
            'task_id': task_id
        }), 200

    except Exception as e:
        logger.error(f"Unexpected error regenerating response: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred. Please try again.'
        }), 500
