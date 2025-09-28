"""
API routes for duplicate detection and other real-time validations
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.services.duplicate_detection import DuplicateDetectionService
from app.models import IdeaPipeline
from app import db
from datetime import datetime, timezone
from app.utils.time_utils import now_utc

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/server-time')
def server_time():
    """Return current server time for timer synchronization"""
    return jsonify({
        'server_time': now_utc().isoformat()
    })


@api_bp.route('/check-duplicates', methods=['POST'])
@login_required
def check_duplicates():
    """Real-time duplicate detection API endpoint"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        ticker_symbol = data.get('ticker_symbol', '').strip()
        entity_type = data.get('entity_type', 'company')

        # Initialize duplicate detection service
        detector = DuplicateDetectionService(current_user.id)

        if entity_type == 'company':
            result = detector.check_company_duplicates(name, ticker_symbol)
        elif entity_type == 'idea':
            result = detector.check_idea_duplicates(name, ticker_symbol)
        else:
            return jsonify({'error': 'Invalid entity_type'}), 400

        # Convert model objects to dictionaries for JSON serialization
        def serialize_entity(entity):
            """Convert model object to dictionary"""
            if hasattr(entity, 'name'):  # Company or Idea
                return {
                    'id': entity.id,
                    'name': entity.name,
                    'ticker_symbol': getattr(entity, 'ticker_symbol', None),
                    'status': getattr(entity, 'status', None),
                    'kill_reason': getattr(entity, 'kill_reason', None)
                }
            return None

        # Serialize exact matches
        for match in result['exact_matches']:
            if 'company' in match:
                match['company'] = serialize_entity(match['company'])
            if 'idea' in match:
                match['idea'] = serialize_entity(match['idea'])

        # Serialize similar matches
        for match in result['similar_matches']:
            if 'company' in match:
                match['company'] = serialize_entity(match['company'])
            if 'idea' in match:
                match['idea'] = serialize_entity(match['idea'])

        # Serialize suggestions
        for suggestion in result['suggestions']:
            if 'company' in suggestion:
                suggestion['company'] = serialize_entity(suggestion['company'])
            if 'idea' in suggestion:
                suggestion['idea'] = serialize_entity(suggestion['idea'])

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/ideas/<int:idea_id>/resurrect', methods=['POST'])
@login_required
def resurrect_idea(idea_id):
    """Resurrect a killed idea"""
    try:
        idea = IdeaPipeline.query.get_or_404(idea_id)

        # Verify ownership
        if idea.user_id != current_user.id:
            return jsonify({'error': 'Access denied'}), 403

        # Verify it's killed
        if idea.status != 'killed':
            return jsonify({'error': 'Idea is not killed'}), 400

        # Resurrect the idea
        idea.status = 'inbox'
        idea.kill_reason = None
        idea.killed_at = None

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Idea "{idea.name}" has been resurrected and moved to inbox'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500