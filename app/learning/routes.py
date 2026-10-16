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

from flask import render_template, request, jsonify
from flask_login import current_user, login_required
from app import db
from app.models import MistakeLog
from app.learning import learning_bp
from app.utils.time_utils import now_utc
from app.utils.decorators import json_errors
from app.utils.auth_utils import owned_or_404

@learning_bp.route('/mistakes')
@login_required
def mistake_log():
    """View and manage mistake log"""
    mistakes = current_user.mistake_logs.order_by(
        MistakeLog.created_at.desc()
    ).all()
    
    # Categorize mistakes
    by_type = {}
    for mistake in mistakes:
        if mistake.mistake_type not in by_type:
            by_type[mistake.mistake_type] = []
        by_type[mistake.mistake_type].append(mistake)
   
   # Calculate total cost
    total_cost = sum(m.cost_estimate or 0 for m in mistakes)
    
    # Most common mistake type
    if by_type:
        most_common_type = max(by_type, key=lambda k: len(by_type[k]))
        most_common_count = len(by_type[most_common_type])
    else:
        most_common_type = None
        most_common_count = 0
    
    return render_template('mistake_log.html',
                            title="Mistake Log",
                            mistakes=mistakes,
                            by_type=by_type,
                            total_cost=total_cost,
                            most_common_type=most_common_type,
                            most_common_count=most_common_count)

@learning_bp.route('/mistakes/<int:mistake_id>/review', methods=['POST'])
@login_required
@json_errors
def review_mistake(mistake_id):
   """Mark a mistake as reviewed"""
   mistake = owned_or_404(MistakeLog, mistake_id)
   
   mistake.times_reviewed += 1
   mistake.last_reviewed = now_utc()
   
   # Check if similar mistake was prevented
   prevented = (request.get_json(silent=True) or {}).get('prevented_similar', False)
   if prevented:
       mistake.prevented_similar += 1
   
   db.session.commit()
   return jsonify({
       'success': True,
       'times_reviewed': mistake.times_reviewed,
       'prevented_similar': mistake.prevented_similar
   })
