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

import json
from collections import Counter
from typing import Optional

from app import db
from app.models import JournalEntry, ResearchProject
from app.utils.blocknote_utils import blocknote_to_text

RED_FLAG = 'red_flag'
GREEN_FLAG = 'green_flag'
MUST_EXIT = 'must_exit'
FINDING_TYPES = (RED_FLAG, GREEN_FLAG, MUST_EXIT)

FINDING_LABELS = {
    RED_FLAG: 'Red Flag',
    GREEN_FLAG: 'Green Flag',
    MUST_EXIT: 'Must Exit',
}

_TYPE_ALIASES = {
    'red': RED_FLAG, 'red_flag': RED_FLAG, 'red-flag': RED_FLAG,
    'green': GREEN_FLAG, 'green_flag': GREEN_FLAG, 'green-flag': GREEN_FLAG,
    'must_exit': MUST_EXIT, 'must-exit': MUST_EXIT, 'must_exit_criteria': MUST_EXIT,
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
    return _TYPE_ALIASES.get(raw.strip().lower())


def finding_text_from_editor(content: Optional[str]) -> str:
    """Findings are plain text; the journal editor posts BlockNote JSON."""
    content = (content or '').strip()
    try:
        blocks = json.loads(content)
    except (json.JSONDecodeError, TypeError, ValueError):
        return content
    return blocknote_to_text(content).strip() if isinstance(blocks, list) else content


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


def _expire_cached_findings(user_id: int, company_id: int) -> None:
    """Make loaded projects re-read their findings (see ResearchProject.finding_journal_entries)."""
    for obj in list(db.session.identity_map.values()):
        if (isinstance(obj, ResearchProject) and obj.user_id == user_id
                and obj.company_id == company_id):
            db.session.expire(obj, ['finding_journal_entries'])


def delete_finding(entry: JournalEntry) -> None:
    db.session.delete(entry)
    _expire_cached_findings(entry.user_id, entry.company_id)


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
    _expire_cached_findings(user_id, company_id)
    return entry


def _clean_lines(texts) -> list:
    return [t.strip() for t in texts or [] if t and t.strip()]


def replace_findings(user_id: int, company_id: int, finding_type: str, texts,
                     project_id: Optional[int] = None, loaded=None) -> None:
    """Apply an edited list of one finding type to the company.

    `loaded` is the list the form showed when it was opened. Only the edits made
    against it are applied, so findings added elsewhere since then survive.
    Without it the stored findings are the baseline (a full replace). Kept
    entries keep their original dates; new texts are added in order.
    """
    wanted = _clean_lines(texts)
    entries = finding_entries(user_id, company_id, finding_type)
    baseline = _clean_lines(loaded) if loaded is not None else [e.content for e in entries]

    removed = Counter(baseline) - Counter(wanted)
    for entry in entries:
        if removed[entry.content] > 0:
            removed[entry.content] -= 1
            delete_finding(entry)

    added = Counter(wanted) - Counter(baseline)
    present = Counter(e.content for e in entries)
    for text in wanted:
        if added[text] > 0:
            added[text] -= 1
            if present[text] > 0:  # already recorded elsewhere since the form loaded
                present[text] -= 1
                continue
            add_finding(user_id, company_id, finding_type, text, project_id=project_id)
