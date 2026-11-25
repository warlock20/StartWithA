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
Actions behind the Research effectiveness finding cards (#440): suggest a kill-checklist
criterion from a finding, and mark a finding as noise.

Both re-derive the finding from the server's own numbers by key; nothing the browser sends
besides the key is trusted. Both flush and leave the commit to the caller.
"""

from typing import Tuple

from app import db
from app.models import KillChecklistSuggestion, ResearchEffectivenessDismissal
from app.services.decision_intelligence import DecisionIntelligenceService
from app.services.kill_criterion_suggester import QUESTION_MAX_LENGTH, default_kill_checklist
from app.services.research_effectiveness import Finding

TRIGGER_EVENT = 'research_effectiveness'
TITLE_MAX_LENGTH = 200
RED_FLAG_QUESTION = 'Before buying, are all red flags on this company resolved?'


class NoKillChecklist(Exception):
    """The user has no kill checklist to add a suggestion to."""


class FindingChanged(Exception):
    """The finding is gone, or no longer supports the action."""


def suggestion_question(finding: Finding) -> str:
    if finding.kind == 'checklist':
        question = f'Before buying, is “{finding.title}” satisfied?'
    else:
        question = RED_FLAG_QUESTION
    return question[:QUESTION_MAX_LENGTH]


def _found(user_id: int, key: str):
    found = DecisionIntelligenceService(user_id).find_finding(key)
    if found is None:
        raise FindingChanged(key)
    return found


def suggest_from_finding(user_id: int, key: str) -> Tuple[KillChecklistSuggestion, bool]:
    """A pending add-criterion suggestion for this finding, as (suggestion, created)."""
    finding, counts = _found(user_id, key)
    if not finding.worse_with_risk:
        raise FindingChanged(key)
    checklist = default_kill_checklist(user_id)
    if checklist is None:
        raise NoKillChecklist()

    pending = KillChecklistSuggestion.query.filter_by(
        user_id=user_id, status='pending', trigger_event=TRIGGER_EVENT,
    ).all()
    for existing in pending:
        if (existing.source_data or {}).get('finding_key') == key:
            return existing, False

    question = suggestion_question(finding)
    small = ', small sample' if finding.small_sample else ''
    suggestion = KillChecklistSuggestion(
        user_id=user_id,
        kill_checklist_id=checklist.id,
        suggestion_type='add_criterion',
        title=f'Add “{question}”'[:TITLE_MAX_LENGTH],
        description=finding.body,
        reasoning=f'From Research effectiveness: {finding.risk.count + finding.base.count} trades{small}.',
        suggestion_data={'new_criterion': {'question': question, 'suggested_position': checklist.criteria_count + 1}},
        effectiveness_gain=0.0,
        trigger_event=TRIGGER_EVENT,
        source_data={
            'finding_key': key, 'counts': counts, 'strength': finding.strength,
            'small_sample': finding.small_sample,
        },
    )
    db.session.add(suggestion)
    db.session.flush()
    return suggestion, True


def mark_as_noise(user_id: int, key: str) -> ResearchEffectivenessDismissal:
    """Hide the finding while its counts in each scope stay as they are now."""
    _, counts = _found(user_id, key)
    dismissal = ResearchEffectivenessDismissal.query.filter_by(user_id=user_id, finding_key=key).first()
    if dismissal is None:
        dismissal = ResearchEffectivenessDismissal(user_id=user_id, finding_key=key, counts=counts)
        db.session.add(dismissal)
    else:
        dismissal.counts = counts
    db.session.flush()
    return dismissal
