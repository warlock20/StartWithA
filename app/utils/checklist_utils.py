"""
Checklist utility functions shared across modules.
Extracted to avoid circular imports between export_service and research_workflow.
"""

from app.models import ChecklistItem


def get_all_ordered_items_for_checklist(checklist_id):
    """
    Returns a flat list of all checklist items for a given checklist_id,
    ordered by their sequence and hierarchy (depth-first).
    """
    return _get_ordered_checklist_items_recursive(None, checklist_id)


def _get_ordered_checklist_items_recursive(parent_item_id, checklist_id):
    """Recursive helper to fetch items and their children in order."""
    ordered_items = []
    if parent_item_id is None:
        items = ChecklistItem.query.filter_by(
            checklist_id=checklist_id, parent_id=None
        ).order_by(ChecklistItem.order).all()
    else:
        items = ChecklistItem.query.filter_by(
            checklist_id=checklist_id, parent_id=parent_item_id
        ).order_by(ChecklistItem.order).all()

    for item in items:
        ordered_items.append(item)
        ordered_items.extend(_get_ordered_checklist_items_recursive(item.id, checklist_id))
    return ordered_items
