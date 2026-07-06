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

import logging
from flask import  request, jsonify, render_template
from flask_login import login_required, current_user

from app import db
from app.portfolio import portfolio_bp
from app.models import DestinationCheckpoint
from app.utils.response_utils import json_success, json_error, json_not_found

from app.constants import DEFAULT_CHECKPOINT_LOOKBACK_DAYS
from app.services.portfolio_intelligence import get_upcoming_checkpoints
from app.services.checkpoint_analysis_service import CheckpointAnalysisService

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

    # Collect all checkpoint IDs and fetch AI insights
    all_checkpoint_ids = []
    for group in checkpoints.values():
        all_checkpoint_ids.extend([cp.id for cp in group])

    checkpoint_insights = CheckpointAnalysisService.get_checkpoint_insights(all_checkpoint_ids)
    analysis_alerts = CheckpointAnalysisService.get_analysis_alerts(checkpoint_insights)

    return render_template('checkpoint_reminders.html',
                          checkpoints=checkpoints,
                          checkpoint_insights=checkpoint_insights,
                          analysis_alerts=analysis_alerts)
    
