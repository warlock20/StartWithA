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
Decision journal helpers: the exit-plan snapshot.

A decision journal freezes the company's must-exit rules when it is created, so
later edits or deletes of the rules do not rewrite what was decided. Nothing
here commits; callers own the transaction.

Stored shape (v1):
    {"version": 1, "captured_at": "<UTC ISO, Z>",
     "rules": [{"entry_id", "signal", "text", "created_at"}]}
Rows from before snapshots hold {"legacy_text": str}.
"""

from dataclasses import dataclass, field
from typing import Optional

from app.models import DecisionJournal
from app.services.findings import active_must_exits
from app.utils.time_utils import datetime, ensure_timezone_aware, now_utc

EXIT_PLAN_SNAPSHOT_VERSION = 1
_TS_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


@dataclass
class ExitPlanView:
    rules: list = field(default_factory=list)
    legacy_text: Optional[str] = None
    captured_at: Optional[datetime] = None


def _utc_iso(value: datetime) -> str:
    return ensure_timezone_aware(value).strftime(_TS_FORMAT)


def snapshot_exit_plan(journal: DecisionJournal) -> dict:
    """Freeze the company's active must-exit rules onto the journal and return them."""
    snapshot = {
        'version': EXIT_PLAN_SNAPSHOT_VERSION,
        'captured_at': _utc_iso(now_utc()),
        'rules': [
            {
                'entry_id': entry.id,
                'signal': entry.title,
                'text': entry.content,
                'created_at': _utc_iso(entry.created_at),
            }
            for entry in active_must_exits(journal.user_id, journal.company_id)
        ],
    }
    journal.exit_criteria = snapshot
    return snapshot


def exit_plan_view(value) -> Optional[ExitPlanView]:
    """Normalise a stored exit_criteria value (v1 dict, legacy dict or plain string)."""
    if value is None:
        return None
    if isinstance(value, str):
        return ExitPlanView(legacy_text=value)
    if not isinstance(value, dict):
        return None
    if 'legacy_text' in value and 'rules' not in value:
        return ExitPlanView(legacy_text=value['legacy_text'])
    captured = value.get('captured_at')
    captured_at = None
    if captured:
        captured_at = datetime.strptime(captured, _TS_FORMAT).replace(tzinfo=now_utc().tzinfo)
    return ExitPlanView(rules=list(value.get('rules') or []), captured_at=captured_at)
