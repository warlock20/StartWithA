"""
AI Research Assistant Routes

Flask routes for AI-powered research assistance:
- Generate AI challenges, elaborations, and fact-checks
- Store user feedback for quality monitoring
- AJAX-based (no page reloads)

Routes:
- POST /research/ai_assist - Generate AI response
- POST /research/ai_assist/feedback - Store user feedback
"""

import logging
from flask import jsonify, request
from flask_login import current_user, login_required

from app import db
from app.research import research_bp
from app.models import ChecklistAnalysis, ChecklistItem, AIResearchFeedback
from app.services.ai_research_assistant import ai_research_assistant
from app.utils.time_utils import now_utc
from app.utils.decorators import require_ai_tokens

logger = logging.getLogger(__name__)


@research_bp.route('/ai_assist', methods=['POST'])
@login_required
@require_ai_tokens(5000)
def ai_assist():
    """
    Generate AI research assistance response.

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
        "mode": "challenge",
        "response": "Counter-argument: Network effects are weak...",
        "tokens_used": 245,
        "feedback_id": 789  // For tracking feedback later
    }

    Or on error:
    {
        "success": false,
        "error": "Invalid mode 'xyz'"
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
                # Invalid analysis_id or unauthorized
                return jsonify({
                    'success': False,
                    'error': 'Invalid or unauthorized analysis_id'
                }), 403

        # If no analysis context, require company_name in request
        if not company_name:
            company_name = data.get('company_name', 'Unknown Company')

        # Build context data
        context_data = {
            'company_name': company_name
        }

        # Call AI Research Assistant service
        logger.info(
            f"AI assist request: user={current_user.id}, mode={mode}, "
            f"analysis={analysis_id}, item={item_id}, company={company_name}"
        )

        # Generate AI response based on mode
        if mode == 'challenge':
            ai_response = ai_research_assistant.generate_challenge(
                question_text=question_text,
                user_answer=answer_text,
                context_data=context_data
            )
        elif mode == 'elaboration':
            ai_response = ai_research_assistant.generate_elaboration(
                question_text=question_text,
                user_answer=answer_text,
                context_data=context_data
            )
        elif mode == 'factcheck':
            ai_response = ai_research_assistant.generate_factcheck(
                question_text=question_text,
                user_answer=answer_text,
                context_data=context_data
            )
        else:
            return jsonify({
                'success': False,
                'error': f"Invalid mode '{mode}'. Valid modes: challenge, elaboration, factcheck"
            }), 400

        # Check if AI service succeeded
        if not ai_response.success:
            logger.error(f"AI assist failed: {ai_response.error}")
            return jsonify({
                'success': False,
                'error': ai_response.error or 'AI service failed'
            }), 500

        # Store interaction in database for quality tracking
        feedback_record = AIResearchFeedback(
            user_id=current_user.id,
            analysis_id=analysis_id,
            item_id=item_id,
            company_name=company_name,
            mode=mode,
            question_text=question_text,
            user_answer=answer_text,
            ai_response=ai_response.response_text,
            tokens_used=ai_response.tokens_used,
            feedback=None,  # User hasn't provided feedback yet
            prompt_version=ai_response.metadata.get('template_version') if ai_response.metadata else None,
            provider='gemini',  # TODO: Get from ai_response.metadata
            model='gemini-flash-latest'  # TODO: Get from ai_response.metadata
        )

        db.session.add(feedback_record)
        db.session.commit()

        # Increment user's token usage with actual tokens from AI response
        current_user.increment_ai_tokens(ai_response.tokens_used)

        logger.info(
            f"AI assist success: feedback_id={feedback_record.id}, "
            f"tokens={ai_response.tokens_used}, mode={mode}, "
            f"user_total={current_user.ai_tokens_used}/{current_user.ai_tokens_limit}"
        )

        # Return success response
        return jsonify({
            'success': True,
            'mode': mode,
            'response': ai_response.response_text,
            'tokens_used': ai_response.tokens_used,
            'feedback_id': feedback_record.id,  # For later feedback submission
            'metadata': {
                'question_length': len(question_text),
                'answer_length': len(answer_text),
                'response_length': len(ai_response.response_text)
            }
        }), 200

    except Exception as e:
        logger.error(f"Unexpected error in AI assist: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred. Please try again.'
        }), 500


@research_bp.route('/ai_assist/feedback', methods=['POST'])
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


@research_bp.route('/ai_assist/regenerate', methods=['POST'])
@login_required
@require_ai_tokens(5000)
def ai_assist_regenerate():
    """
    Regenerate AI response for the same question/answer.

    Useful when user clicks "Regenerate" button after getting
    a not-so-helpful response.

    Request Body (JSON):
    {
        "feedback_id": 789
    }

    Response (JSON):
    Same as /ai_assist endpoint
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

        # Re-use original parameters to regenerate
        context_data = {
            'company_name': original_record.company_name or 'Unknown Company'
        }

        # Generate new AI response
        if original_record.mode == 'challenge':
            ai_response = ai_research_assistant.generate_challenge(
                question_text=original_record.question_text,
                user_answer=original_record.user_answer,
                context_data=context_data
            )
        elif original_record.mode == 'elaboration':
            ai_response = ai_research_assistant.generate_elaboration(
                question_text=original_record.question_text,
                user_answer=original_record.user_answer,
                context_data=context_data
            )
        elif original_record.mode == 'factcheck':
            ai_response = ai_research_assistant.generate_factcheck(
                question_text=original_record.question_text,
                user_answer=original_record.user_answer,
                context_data=context_data
            )
        else:
            return jsonify({
                'success': False,
                'error': f"Invalid mode '{original_record.mode}'"
            }), 400

        if not ai_response.success:
            return jsonify({
                'success': False,
                'error': ai_response.error or 'AI service failed'
            }), 500

        # Create NEW feedback record for regenerated response
        new_feedback_record = AIResearchFeedback(
            user_id=current_user.id,
            analysis_id=original_record.analysis_id,
            item_id=original_record.item_id,
            company_name=original_record.company_name,
            mode=original_record.mode,
            question_text=original_record.question_text,
            user_answer=original_record.user_answer,
            ai_response=ai_response.response_text,
            tokens_used=ai_response.tokens_used,
            feedback=None,
            prompt_version=ai_response.metadata.get('template_version') if ai_response.metadata else None,
            provider='gemini',
            model='gemini-flash-latest'
        )

        db.session.add(new_feedback_record)
        db.session.commit()

        # Increment user's token usage with actual tokens from AI response
        current_user.increment_ai_tokens(ai_response.tokens_used)

        logger.info(
            f"AI response regenerated: original_id={feedback_id}, "
            f"new_id={new_feedback_record.id}, mode={original_record.mode}, "
            f"tokens={ai_response.tokens_used}, user_total={current_user.ai_tokens_used}/{current_user.ai_tokens_limit}"
        )

        return jsonify({
            'success': True,
            'mode': original_record.mode,
            'response': ai_response.response_text,
            'tokens_used': ai_response.tokens_used,
            'feedback_id': new_feedback_record.id,
            'regenerated_from': feedback_id
        }), 200

    except Exception as e:
        logger.error(f"Unexpected error regenerating response: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred. Please try again.'
        }), 500
