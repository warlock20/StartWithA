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
What a market-sweep row should say about a company, for one user.

The row itself holds a decision made at one moment; the company keeps moving
afterwards. So the row's status is derived on read from the linked company's
state rather than stored -- a stored copy is exactly what goes stale.

Where no link exists there is nothing to derive, and a name match is only ever
offered as a suggestion. Rendering never creates or repoints a link.
"""

import logging

from app.services.company_state import company_states
from app.services.sweep_link import links_for, suggestions_for
from app.models.market_sweep import MarketSweepCompany

logger = logging.getLogger(__name__)

#: A row with nothing known about it. Shared so callers can compare against it.
EMPTY_ROW = {'state': None, 'link': None, 'suggestion': None}


def sweep_row_display(user_id, sweep_id):
    """Everything the sweep page needs about every row, in a fixed set of queries.

    Returns {sweep_company_id: {'state', 'link', 'suggestion'}}. A row has a
    state only when a stored link says which company it is; otherwise it may
    carry a suggestion, which is a candidate and not an answer.
    """
    row_ids = [
        row_id for (row_id,) in
        MarketSweepCompany.query.with_entities(MarketSweepCompany.id)
        .filter_by(sweep_id=sweep_id).all()
    ]

    links = links_for(user_id, sweep_id)
    states = company_states(user_id, {l['company_id'] for l in links.values()})
    suggestions = suggestions_for(user_id, sweep_id)

    display = {}
    for row_id in row_ids:
        link = links.get(row_id)
        state = states.get(link['company_id']) if link else None
        candidates = suggestions.get(row_id) or []

        display[row_id] = {
            'state': {
                'key': state.key,
                'label': state.label,
                'stage': state.stage,
                'is_dead': state.is_dead,
                'reason': state.reason,
            } if state else None,
            'link': dict(link) if link else None,
            # Best first, and only when the row has no link -- a linked row's
            # question is already answered.
            'suggestion': candidates[0] if candidates and not link else None,
        }

    return display
