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
from flask import request, render_template
from flask_login import login_required, current_user

from app import db
from app.portfolio import portfolio_bp
from app.models import DestinationCheckpoint
from app.utils.response_utils import json_success, json_error, json_not_found
from app.utils.decorators import json_errors

from app.services.checkpoints_page import CheckpointsPageService
from app.services.exit_watch import episodes as exit_episodes
from app.utils.time_utils import now_utc

logger = logging.getLogger(__name__)

@portfolio_bp.route('/checkpoint/<int:checkpoint_id>/update-status', methods=['POST'])
@login_required
@json_errors
def update_checkpoint_status(checkpoint_id):
    """Update the status of a destination checkpoint"""
    data = request.get_json(silent=True) or {}
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

@portfolio_bp.route('/checkpoints')
@login_required
def checkpoint_reminders():
    """Checkpoints page: what needs action, then every position or every checkpoint by date."""
    # Exit-rule episodes first, committing only on a change, so the loads below stay loaded
    if exit_episodes.resolve(current_user.id, now_utc()):
        db.session.commit()

    view = 'date' if request.args.get('view') == 'date' else 'position'
    return render_template('checkpoint_reminders.html', view=view,
                           page=CheckpointsPageService(current_user.id))
