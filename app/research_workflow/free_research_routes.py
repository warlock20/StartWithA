"""
Free Research Step API Routes

AJAX endpoints for managing free-form research questions within a research project step.
"""

from flask import jsonify, request
from flask_login import current_user, login_required
from app import db
from app.models import ResearchProject
from app.models.research import FreeResearchQuestion, ModelQuestion
from app.research_workflow import research_workflow_bp
from app.utils.time_utils import now_utc
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Free Research Questions CRUD
# =============================================================================

@research_workflow_bp.route('/api/project/<int:project_id>/step/<int:step_index>/questions')
@login_required
def get_free_research_questions(project_id, step_index):
    """Get all questions for a free research step"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Access denied'}), 403

    questions = FreeResearchQuestion.query.filter_by(
        project_id=project_id,
        step_index=step_index
    ).order_by(FreeResearchQuestion.order_index).all()

    return jsonify({
        'success': True,
        'questions': [{
            'id': q.id,
            'question_text': q.question_text,
            'answer_content': q.answer_content,
            'status': q.status,
            'order_index': q.order_index,
            'created_at': q.created_at.isoformat() if q.created_at else None,
            'answered_at': q.answered_at.isoformat() if q.answered_at else None
        } for q in questions],
        'stats': {
            'total': len(questions),
            'answered': sum(1 for q in questions if q.status == 'answered'),
            'exploring': sum(1 for q in questions if q.status == 'exploring')
        }
    })


@research_workflow_bp.route('/api/project/<int:project_id>/step/<int:step_index>/questions', methods=['POST'])
@login_required
def add_free_research_question(project_id, step_index):
    """Add a new question to a free research step"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Access denied'}), 403

    data = request.get_json()
    if not data or not data.get('question_text'):
        return jsonify({'success': False, 'error': 'Question text is required'}), 400

    # Get the next order index
    max_order = db.session.query(db.func.max(FreeResearchQuestion.order_index)).filter_by(
        project_id=project_id,
        step_index=step_index
    ).scalar() or -1

    question = FreeResearchQuestion(
        user_id=current_user.id,
        project_id=project_id,
        step_index=step_index,
        question_text=data['question_text'].strip(),
        status='exploring',
        order_index=max_order + 1
    )

    db.session.add(question)
    db.session.commit()

    logger.info(f"User {current_user.id} added question {question.id} to project {project_id} step {step_index}")

    return jsonify({
        'success': True,
        'question': {
            'id': question.id,
            'question_text': question.question_text,
            'answer_content': question.answer_content,
            'status': question.status,
            'order_index': question.order_index,
            'created_at': question.created_at.isoformat()
        }
    })


@research_workflow_bp.route('/api/questions/<int:question_id>', methods=['PUT'])
@login_required
def update_free_research_question(question_id):
    """Update a question's answer or status"""
    question = FreeResearchQuestion.query.get_or_404(question_id)

    if question.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Access denied'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    # Update fields if provided
    if 'answer_content' in data:
        question.answer_content = data['answer_content']

    if 'status' in data:
        old_status = question.status
        question.status = data['status']
        # Track when answered
        if data['status'] == 'answered' and old_status != 'answered':
            question.answered_at = now_utc()
        elif data['status'] == 'exploring':
            question.answered_at = None

    if 'question_text' in data:
        question.question_text = data['question_text'].strip()

    question.updated_at = now_utc()
    db.session.commit()

    return jsonify({
        'success': True,
        'question': {
            'id': question.id,
            'question_text': question.question_text,
            'answer_content': question.answer_content,
            'status': question.status,
            'updated_at': question.updated_at.isoformat()
        }
    })


@research_workflow_bp.route('/api/questions/<int:question_id>', methods=['DELETE'])
@login_required
def delete_free_research_question(question_id):
    """Delete a question"""
    question = FreeResearchQuestion.query.get_or_404(question_id)

    if question.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Access denied'}), 403

    db.session.delete(question)
    db.session.commit()

    logger.info(f"User {current_user.id} deleted question {question_id}")

    return jsonify({'success': True})


@research_workflow_bp.route('/api/project/<int:project_id>/step/<int:step_index>/questions/reorder', methods=['POST'])
@login_required
def reorder_free_research_questions(project_id, step_index):
    """Reorder questions via drag and drop"""
    project = ResearchProject.query.get_or_404(project_id)

    if project.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Access denied'}), 403

    data = request.get_json()
    if not data or 'question_ids' not in data:
        return jsonify({'success': False, 'error': 'Question IDs required'}), 400

    # Update order based on new positions
    for index, question_id in enumerate(data['question_ids']):
        question = FreeResearchQuestion.query.get(question_id)
        if question and question.user_id == current_user.id:
            question.order_index = index

    db.session.commit()

    return jsonify({'success': True})


# =============================================================================
# Model Questions Library
# =============================================================================

@research_workflow_bp.route('/api/model-questions')
@login_required
def get_model_questions():
    """Get user's model questions library"""
    questions = ModelQuestion.query.filter_by(
        user_id=current_user.id
    ).order_by(ModelQuestion.times_used.desc()).all()

    return jsonify({
        'success': True,
        'questions': [{
            'id': q.id,
            'question_text': q.question_text,
            'category': q.category,
            'times_used': q.times_used,
            'created_at': q.created_at.isoformat() if q.created_at else None,
            'last_used_at': q.last_used_at.isoformat() if q.last_used_at else None
        } for q in questions]
    })


@research_workflow_bp.route('/api/model-questions', methods=['POST'])
@login_required
def create_model_question():
    """Save a question to the model questions library"""
    data = request.get_json()
    if not data or not data.get('question_text'):
        return jsonify({'success': False, 'error': 'Question text is required'}), 400

    # Check for duplicate
    existing = ModelQuestion.query.filter_by(
        user_id=current_user.id,
        question_text=data['question_text'].strip()
    ).first()

    if existing:
        return jsonify({'success': False, 'error': 'This question already exists in your library'}), 400

    model_question = ModelQuestion(
        user_id=current_user.id,
        question_text=data['question_text'].strip(),
        category=data.get('category'),
        source_project_id=data.get('source_project_id')
    )

    db.session.add(model_question)
    db.session.commit()

    logger.info(f"User {current_user.id} saved model question {model_question.id}")

    return jsonify({
        'success': True,
        'question': {
            'id': model_question.id,
            'question_text': model_question.question_text,
            'category': model_question.category,
            'times_used': model_question.times_used
        }
    })


@research_workflow_bp.route('/api/model-questions/<int:question_id>', methods=['DELETE'])
@login_required
def delete_model_question(question_id):
    """Delete a model question from library"""
    question = ModelQuestion.query.get_or_404(question_id)

    if question.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Access denied'}), 403

    db.session.delete(question)
    db.session.commit()

    return jsonify({'success': True})


@research_workflow_bp.route('/api/model-questions/<int:question_id>/use', methods=['POST'])
@login_required
def use_model_question(question_id):
    """Track when a model question is used (inserted into a project)"""
    question = ModelQuestion.query.get_or_404(question_id)

    if question.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Access denied'}), 403

    question.times_used = (question.times_used or 0) + 1
    question.last_used_at = now_utc()
    db.session.commit()

    return jsonify({
        'success': True,
        'times_used': question.times_used
    })
