# Investment Checklist Platform
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
Checklist utility functions shared across modules.
Extracted to avoid circular imports between export_service and research_workflow.
"""

from app.models import ChecklistItem


def get_all_ordered_items_for_checklist(checklist_id):
    """
    Returns a flat list of all checklist items for a given checklist_id,
    ordered by their sequence and hierarchy (depth-first).
    Uses a single query + in-memory sorting instead of recursive queries.
    """
    # Single query: fetch ALL items for this checklist at once
    all_items = ChecklistItem.query.filter_by(
        checklist_id=checklist_id
    ).order_by(ChecklistItem.order).all()

    if not all_items:
        return []

    # Build parent_id -> children map (children already sorted by .order)
    children_map = {}
    for item in all_items:
        children_map.setdefault(item.parent_id, []).append(item)

    # Depth-first traversal from root items (parent_id=None)
    result = []

    def dfs(parent_id):
        for child in children_map.get(parent_id, []):
            result.append(child)
            dfs(child.id)

    dfs(None)
    return result
