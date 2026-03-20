import logging
from flask import  request, jsonify, render_template
from flask_login import login_required, current_user

from app import db
from app.portfolio import portfolio_bp
from app.models import DestinationCheckpoint
from app.utils.response_utils import json_success, json_error, json_not_found

from app.constants import DEFAULT_CHECKPOINT_LOOKBACK_DAYS
from app.services.portfolio_intelligence import get_upcoming_checkpoints

logger = logging.getLogger(__name__)

@portfolio_bp.route('/checkpoint/<int:checkpoint_id>/update-status', methods=['POST'])
@login_required
def update_checkpoint_status(checkpoint_id):
    """Update the status of a destination checkpoint"""
    try:
        data = request.get_json()
        new_status = data.get('status')

        # Validate status
        if new_status not in ['Active', 'Met', 'Not Met']:
            return json_error('Invalid status')

        # Get checkpoint and verify ownership
        checkpoint = DestinationCheckpoint.query.filter_by(
            id=checkpoint_id,
            user_id=current_user.id
        ).first()

        if not checkpoint:
            return json_not_found('Checkpoint')

        # Update status
        checkpoint.status = new_status
        db.session.commit()

        return json_success(f'Checkpoint marked as {new_status}')

    except Exception as e:
        db.session.rollback()
        return json_error(str(e), status_code=500)

@portfolio_bp.route('/checkpoints')
@login_required
def checkpoint_reminders():
    """Checkpoint Reminders Dashboard"""    
    checkpoints = get_upcoming_checkpoints(current_user.id, days_ahead=DEFAULT_CHECKPOINT_LOOKBACK_DAYS)
    
    return render_template('checkpoint_reminders.html',
                          checkpoints=checkpoints)
    
