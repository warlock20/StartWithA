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

"""Resolve which checklist a workflow Checklist step should use (#352)."""

from sqlalchemy.orm.attributes import flag_modified

from app import db
from app.models import Checklist, ChecklistAnalysis
from app.services.export_service import resolve_checklist_id


def _as_int(value):
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None


def owned_checklist(user_id, checklist_id):
    """The user's checklist for this id (str or int), or None."""
    cid = _as_int(checklist_id)
    if not cid:
        return None
    checklist = db.session.get(Checklist, cid)
    if checklist and checklist.user_id == user_id:
        return checklist
    return None


def template_step(project, step_index):
    """The template's step at this index when it is a checklist step, else None."""
    template = project.template
    steps = template.workflow_steps if template else None
    if not steps or not 0 <= step_index < len(steps):
        return None
    step = steps[step_index]
    if isinstance(step, dict) and step.get('type') == 'checklist':
        return step
    return None


def _config_id(step):
    if not isinstance(step, dict):
        return None
    return (step.get('config') or {}).get('checklist_id')


def resolve_step_checklist(project, step_index, step, user_id):
    """Pick the checklist for a Checklist step.

    Returns (checklist, source); source is one of 'override', 'snapshot',
    'template', 'analysis', 'only_checklist', or None when nothing resolves.
    """
    overrides = project.step_overrides or {}
    override = overrides.get(str(step_index)) or {}
    candidates = (
        ('override', override.get('checklist_id')),
        ('snapshot', _config_id(step)),
        ('template', _config_id(template_step(project, step_index))),
    )
    for source, raw_id in candidates:
        checklist = owned_checklist(user_id, raw_id)
        if checklist:
            return checklist, source

    if project.company_id:
        taken = {
            resolve_checklist_id(project, index, other)
            for index, other in enumerate(project.workflow_steps or [])
            if index != step_index and isinstance(other, dict)
            and other.get('type') == 'checklist'
        }
        analyses = (ChecklistAnalysis.query
                    .filter_by(user_id=user_id, company_id=project.company_id)
                    .order_by(ChecklistAnalysis.start_date.desc())
                    .all())
        for analysis in analyses:
            if _as_int(analysis.checklist_id) in taken:
                continue
            checklist = owned_checklist(user_id, analysis.checklist_id)
            if checklist:
                return checklist, 'analysis'

    mine = Checklist.query.filter_by(user_id=user_id).limit(2).all()
    if len(mine) == 1:
        return mine[0], 'only_checklist'
    return None, None


def record_step_override(project, step_index, checklist_id):
    """Remember the resolved checklist on the project (does not commit)."""
    overrides = dict(project.step_overrides or {})
    overrides[str(step_index)] = {'checklist_id': int(checklist_id)}
    project.step_overrides = overrides
    flag_modified(project, 'step_overrides')


def fill_template_blank(project, step_index, checklist_id, user_id):
    """Bind the template's checklist step when it has no usable binding.

    Returns whether it wrote. Never commits.
    """
    step = template_step(project, step_index)
    if (step is None or not project.template
            or project.template.user_id != user_id
            or owned_checklist(user_id, _config_id(step))):
        return False
    config = dict(step.get('config') or {})
    config['checklist_id'] = int(checklist_id)
    step['config'] = config
    flag_modified(project.template, 'workflow_steps')
    return True
