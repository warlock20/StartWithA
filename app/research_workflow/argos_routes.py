"""
Argos API Routes

Endpoints for Argos intelligent research assistant.
"""

import logging
from flask import jsonify, request, render_template
from flask_login import current_user, login_required

from app import limiter
from app.research_workflow import research_workflow_bp
from app.services.argos import ArgosService, argos_check
from app.constants import RATELIMIT_AI

logger = logging.getLogger(__name__)


@research_workflow_bp.route('/argos/test')
@login_required
def argos_test_page():
    """Test page for Argos Check functionality."""
    return render_template('argos_test.html')


@research_workflow_bp.route('/api/argos/check', methods=['POST'])
@login_required
@limiter.limit(RATELIMIT_AI)
def argos_check_endpoint():
    """
    Perform Argos Check for current research context.

    Request JSON:
        {
            "company_id": 123,
            "step_type": "checklist",  // checklist, free_research, thesis, completion
            "step_context": {"section": "financial"},  // optional
            "current_text": "..."  // optional, for semantic matching
        }

    Response JSON:
        {
            "success": true,
            "result": {
                "insights": [...],
                "checks_passed": [...],
                "checks_failed": [...],
                "summary": {...},
                "meta": {...}
            }
        }
    """
    data = request.get_json() or {}

    # Validate required fields
    company_id = data.get('company_id')
    if not company_id:
        return jsonify({'success': False, 'error': 'company_id required'}), 400

    step_type = data.get('step_type', 'checklist')
    step_context = data.get('step_context', {})
    current_text = data.get('current_text')

    try:
        # Perform Argos Check
        result = argos_check(
            user_id=current_user.id,
            company_id=company_id,
            step_type=step_type,
            step_context=step_context,
        )

        # If current_text provided, do another check with semantic matching
        if current_text:
            argos = ArgosService(user_id=current_user.id)
            result = argos.check(
                company_id=company_id,
                step_type=step_type,
                step_context=step_context,
                current_text=current_text,
            )

        return jsonify({
            'success': True,
            'result': result.to_dict(),
        })

    except Exception as e:
        logger.error(f"Argos check failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@research_workflow_bp.route('/api/argos/feedback', methods=['POST'])
@login_required
def argos_feedback_endpoint():
    """
    Submit feedback for an Argos insight.

    Request JSON:
        {
            "insight_id": "mistake_log_123",
            "feedback": "helpful" | "not_helpful"
        }

    Response JSON:
        {
            "success": true
        }
    """
    data = request.get_json() or {}

    insight_id = data.get('insight_id')
    feedback = data.get('feedback')

    if not insight_id or feedback not in ('helpful', 'not_helpful'):
        return jsonify({
            'success': False,
            'error': 'insight_id and feedback (helpful/not_helpful) required'
        }), 400

    try:
        # Parse insight_id to get source_type and source_id
        # Format: "mistake_log_123" or "trade_loss_456"
        parts = insight_id.rsplit('_', 1)
        if len(parts) != 2:
            return jsonify({'success': False, 'error': 'Invalid insight_id format'}), 400

        source_type = parts[0]
        source_id = int(parts[1])

        # Update feedback in EmbeddingStore or ArgosInsightBase
        # For now, just log it - we'll implement proper storage later
        logger.info(
            f"Argos feedback: user={current_user.id}, "
            f"insight={insight_id}, feedback={feedback}"
        )

        # TODO: Store feedback for algorithm improvement
        # - Update times_helpful or times_not_helpful in ArgosInsightBase
        # - Or store in a separate feedback table

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Argos feedback failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@research_workflow_bp.route('/api/argos/explain', methods=['POST'])
@login_required
def argos_explain_endpoint():
    """
    Get detailed explanation for an Argos insight (LLM-generated).

    Request JSON:
        {
            "insight_id": "mistake_log_123",
            "company_id": 456,
            "current_focus": "management quality"
        }

    Response JSON:
        {
            "success": true,
            "explanation": "..."
        }
    """
    data = request.get_json() or {}

    insight_id = data.get('insight_id')
    company_id = data.get('company_id')

    if not insight_id or not company_id:
        return jsonify({
            'success': False,
            'error': 'insight_id and company_id required'
        }), 400

    try:
        # TODO: Implement LLM explanation generation
        # - Load insight data
        # - Load company data
        # - Call ai_service with argos/explanation.yaml prompt

        return jsonify({
            'success': True,
            'explanation': 'Detailed explanation coming soon...',
        })

    except Exception as e:
        logger.error(f"Argos explain failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
