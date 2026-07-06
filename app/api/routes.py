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
API routes for duplicate detection and other real-time validations
"""

from datetime import datetime, timezone
from flask import request, jsonify, session
from app.utils.response_utils import json_error, json_unauthorized
from flask_login import login_required, current_user
from sqlalchemy.orm.attributes import flag_modified
from app import db
from app.api import api_bp
from app.models import IdeaPipeline
from app.services.duplicate_detection import DuplicateDetectionService
from app.utils.time_utils import now_utc


@api_bp.route('/server-time')
@login_required
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
            return json_error('Invalid entity_type')

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
        return json_error(str(e), status_code=500)


@api_bp.route('/ideas/<int:idea_id>/resurrect', methods=['POST'])
@login_required
def resurrect_idea(idea_id):
    """Resurrect a killed idea"""
    try:
        idea = IdeaPipeline.query.get_or_404(idea_id)

        # Verify ownership
        if idea.user_id != current_user.id:
            return json_unauthorized('Access denied')

        # Verify it's killed
        if idea.status != 'killed':
            return json_error('Idea is not killed')

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
        return json_error(str(e), status_code=500)


@api_bp.route('/mark-tour-completed', methods=['POST'])
@login_required
def mark_tour_completed():
    """Mark a tour as completed for the current user"""
    try:
        data = request.get_json()
        tour_name = data.get('tour_name')

        if not tour_name:
            return json_error('tour_name is required')

        # Get or initialize page_tours_completed dict
        if current_user.page_tours_completed is None:
            current_user.page_tours_completed = {}

        # Mark tour as completed
        tours_completed = current_user.page_tours_completed.copy()
        tours_completed[tour_name] = True
        current_user.page_tours_completed = tours_completed

        # Mark flag to trigger JSONB update
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(current_user, 'page_tours_completed')

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Tour "{tour_name}" marked as completed'
        })

    except Exception as e:
        db.session.rollback()
        return json_error(str(e), status_code=500)


@api_bp.route('/should-show-tour', methods=['GET'])
@login_required
def should_show_tour():
    """Check if a tour should be shown to the current user"""
    try:
        tour_name = request.args.get('tour_name')

        if not tour_name:
            return json_error('tour_name is required')

        # Check user preferences
        show_tours = True
        if current_user.tour_preferences:
            show_tours = current_user.tour_preferences.get('show_page_tours', True)

        # Check if tour was already completed
        tour_completed = False
        if current_user.page_tours_completed:
            tour_completed = current_user.page_tours_completed.get(tour_name, False)

        # Show tour if: preferences allow AND tour not completed
        should_show = show_tours and not tour_completed

        return jsonify({
            'should_show': should_show,
            'tour_completed': tour_completed,
            'show_tours_enabled': show_tours
        })

    except Exception as e:
        return json_error(str(e), status_code=500)


@api_bp.route('/dismiss-quote-banner', methods=['POST'])
@login_required
def dismiss_quote_banner():
    """Dismiss the quote banner for the current session"""
    try:
        session['quote_banner_dismissed'] = True

        return jsonify({
            'success': True,
            'message': 'Quote banner dismissed for this session'
        })

    except Exception as e:
        return json_error(str(e), status_code=500)