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

"""Review the expected returns saved before they became CAGRs.

The expected return used to be read as a total over the expected timeframe, and
Update Thesis asked for a total. It is now a CAGR. Over 12 months (or with no
timeframe) a total and a CAGR read the same, so the expected_cagr_rename
migration queued only the other entries in ExpectedCagrReview. Each is resolved
once: converted (the original value was a total), set to a new CAGR, or kept
(it was already a CAGR). Converting always starts from the original value, so
running it again gives the same result.
"""

from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Optional

from app import db
from app.models import DecisionJournal, ExpectedCagrReview, ThesisEvolution
from app.services.outcome_tracking import safe_sync_outcomes
from app.utils.time_utils import now_utc

BUY = 'buy'
THESIS = 'thesis'
KINDS = (BUY, THESIS)
CONVERTED = 'converted'
SET = 'set'
KEPT = 'kept'
SOURCE_NOTES = {
    BUY: 'buy form (did not say total or annual)',
    THESIS: 'Update Thesis (asked for a total return)',
}


def cagr_from_total(total_pct: float, months: int) -> float:
    """The annual rate (CAGR, %) that compounds to total_pct over months."""
    growth = max(1 + float(total_pct) / 100, 0.0)
    return round((growth ** (12 / months) - 1) * 100, 2)


def _load_entry(kind: str, entry_id: int):
    model = DecisionJournal if kind == BUY else ThesisEvolution
    return db.session.get(model, entry_id)


def _company_label(entry) -> str:
    company = entry.company if entry is not None else None
    label = f'{company.ticker_symbol} {company.name}' if company else '?'
    if isinstance(entry, ThesisEvolution):
        label += f' V{entry.version}'
    return label


def _entered_on(entry) -> Optional[date]:
    if isinstance(entry, DecisionJournal):
        return entry.decision_date
    return entry.created_at.date() if entry is not None and entry.created_at else None


@dataclass
class ReviewEntry:
    kind: str
    id: int
    user_id: int
    company: str
    entered_on: Optional[date]
    original_value: float  # As saved before the rename
    current_value: Optional[float]  # None when the entry no longer has one, or is gone
    timeframe_months: int
    cagr_if_total: float  # What convert would store
    note: str


def review_entries(user_id: Optional[int] = None) -> List[ReviewEntry]:
    """The queued entries not resolved yet, oldest first."""
    rows = ExpectedCagrReview.query.filter(ExpectedCagrReview.resolution.is_(None))
    if user_id is not None:
        rows = rows.filter(ExpectedCagrReview.user_id == user_id)
    entries = []
    for row in rows.order_by(ExpectedCagrReview.user_id, ExpectedCagrReview.kind, ExpectedCagrReview.entry_id):
        entry = _load_entry(row.kind, row.entry_id)
        entries.append(ReviewEntry(
            row.kind, row.entry_id, row.user_id, _company_label(entry), _entered_on(entry),
            row.original_value, entry.expected_cagr if entry is not None else None,
            row.timeframe_months, cagr_from_total(row.original_value, row.timeframe_months),
            SOURCE_NOTES.get(row.kind, row.kind)))
    entries.sort(key=lambda e: (e.user_id, e.entered_on or date.min, e.kind, e.id))
    return entries


@dataclass
class FixResult:
    kind: str
    id: int
    old: Optional[float]
    new: Optional[float]
    error: Optional[str] = None


def _store(entry, value: float):
    if isinstance(entry, DecisionJournal):
        entry.expected_cagr = value
        # research_outcome copies the BUY decision's expected CAGR
        safe_sync_outcomes(entry.user_id, entry.company_id)
    else:
        # Reassign so SQLAlchemy sees the JSON change
        entry.key_metrics = {**(entry.key_metrics or {}), 'expected_cagr': value}


def _resolve(kind: str, entry_id: int, resolution: str, value: Optional[float]) -> FixResult:
    row = ExpectedCagrReview.query.filter_by(kind=kind, entry_id=entry_id).first()
    if row is None:
        return FixResult(kind, entry_id, None, None, 'not on the review list')
    entry = _load_entry(kind, entry_id)
    if entry is None:
        return FixResult(kind, entry_id, None, None, 'the entry no longer exists')
    current = entry.expected_cagr

    if resolution == CONVERTED:
        if row.resolution == CONVERTED:
            return FixResult(kind, entry_id, current, current)  # Already done; nothing changes
        if current != row.original_value:
            return FixResult(kind, entry_id, current, None,
                             f'changed since the migration (was {row.original_value}); use set or keep')
        value = cagr_from_total(row.original_value, row.timeframe_months)
    elif resolution == KEPT:
        value = current

    if value != current:
        _store(entry, float(value))
    row.resolution = resolution
    row.resolved_value = value
    row.resolved_at = now_utc()
    return FixResult(kind, entry_id, current, value)


def _apply(items, resolution: str, dry_run: bool) -> List[FixResult]:
    results = [_resolve(kind, entry_id, resolution, value) for kind, entry_id, value in items]
    if dry_run or any(r.error for r in results):
        db.session.rollback()
    else:
        db.session.commit()
    return results


def convert_totals(items: Iterable[tuple], dry_run: bool = False) -> List[FixResult]:
    """(kind, id) entries whose original value was a total: store its CAGR."""
    return _apply([(kind, entry_id, None) for kind, entry_id in items], CONVERTED, dry_run)


def set_values(items: Iterable[tuple], dry_run: bool = False) -> List[FixResult]:
    """(kind, id, value) entries: store value as the expected CAGR."""
    return _apply([(kind, entry_id, float(value)) for kind, entry_id, value in items], SET, dry_run)


def keep_values(items: Iterable[tuple], dry_run: bool = False) -> List[FixResult]:
    """(kind, id) entries that were already a CAGR: leave the value, take them off the list."""
    return _apply([(kind, entry_id, None) for kind, entry_id in items], KEPT, dry_run)
