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
Company findings: red flags, green flags and must-exit criteria.

Findings are journal entries on the company, so they can be recorded with or
without a research project. When the company has a research project the entry
is linked to it as well. Nothing here commits; callers own the transaction.
"""

from typing import Optional

from app import db
from app.models import JournalEntry, ResearchProject

RED_FLAG = 'red_flag'
GREEN_FLAG = 'green_flag'
MUST_EXIT = 'must_exit'
FINDING_TYPES = (RED_FLAG, GREEN_FLAG, MUST_EXIT)

FINDING_LABELS = {
    RED_FLAG: 'Red Flag',
    GREEN_FLAG: 'Green Flag',
    MUST_EXIT: 'Must Exit',
}

_SENTIMENT = {
    RED_FLAG: 'bearish',
    GREEN_FLAG: 'bullish',
    MUST_EXIT: None,
}


def normalize_finding_type(raw: Optional[str]) -> Optional[str]:
    """Map 'red', 'red_flag', 'green', 'must_exit', ... to a finding type."""
    if not raw:
        return None
    raw = raw.strip().lower()
    if 'must_exit' in raw or 'must-exit' in raw:
        return MUST_EXIT
    if 'green' in raw:
        return GREEN_FLAG
    if 'red' in raw:
        return RED_FLAG
    return None


def finding_entries(user_id: int, company_id: int, finding_type: Optional[str] = None):
    """Findings for a company, oldest first."""
    types = [finding_type] if finding_type else list(FINDING_TYPES)
    return JournalEntry.query.filter(
        JournalEntry.user_id == user_id,
        JournalEntry.company_id == company_id,
        JournalEntry.entry_type.in_(types),
        db.or_(JournalEntry.is_archived.is_(False), JournalEntry.is_archived.is_(None)),
    ).order_by(JournalEntry.created_at.asc(), JournalEntry.id.asc()).all()


def finding_texts(user_id: int, company_id: int, finding_type: str) -> list:
    return [e.content for e in finding_entries(user_id, company_id, finding_type)]


def _project_id_for(user_id: int, company_id: int) -> Optional[int]:
    project = ResearchProject.query.filter_by(
        user_id=user_id, company_id=company_id
    ).with_entities(ResearchProject.id).first()
    return project.id if project else None


def add_finding(user_id: int, company_id: int, finding_type: str, text: str,
                project_id: Optional[int] = None) -> JournalEntry:
    """Record one finding as a journal entry."""
    if finding_type not in FINDING_TYPES:
        raise ValueError(f'Invalid finding type: {finding_type}')
    text = (text or '').strip()
    if not text:
        raise ValueError('Finding text is required')

    if project_id is None:
        project_id = _project_id_for(user_id, company_id)

    entry = JournalEntry(
        user_id=user_id,
        company_id=company_id,
        project_id=project_id,
        entry_type=finding_type,
        title=FINDING_LABELS[finding_type],
        content=text,
        sentiment=_SENTIMENT[finding_type],
        source='finding',
    )
    db.session.add(entry)
    return entry


def replace_findings(user_id: int, company_id: int, finding_type: str, texts,
                     project_id: Optional[int] = None) -> None:
    """Make the company's findings of one type match `texts`.

    Entries whose text is still listed are kept (with their original dates);
    the rest are deleted and new texts are added in order.
    """
    wanted = [t.strip() for t in texts if t and t.strip()]
    remaining = list(wanted)
    for entry in finding_entries(user_id, company_id, finding_type):
        if entry.content in remaining:
            remaining.remove(entry.content)
        else:
            db.session.delete(entry)
    for text in remaining:
        add_finding(user_id, company_id, finding_type, text, project_id=project_id)
