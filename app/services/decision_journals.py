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
Decision journal helpers: the exit-plan snapshot and opening vs. top-up lookup.

A decision journal freezes the company's must-exit rules when it is created, so
later edits or deletes of the rules do not rewrite what was decided. Every buy is
its own decision: the one that opens a holding period (round trip) is the opening
decision, and each later buy in the period is a top-up pointing to it through
parent_decision_id. Nothing here commits; callers own the transaction.

Stored shape (v1):
    {"version": 1, "captured_at": "<UTC ISO, Z>",
     "rules": [{"entry_id", "signal", "text", "created_at"}]}
Rows from before snapshots hold {"legacy_text": str}.
"""

from dataclasses import dataclass, field
from typing import Optional

from app.models import DecisionJournal, ThesisEvolution, Transaction
from app.models.portfolio import RoundTrip, get_round_trips
from app.services.findings import active_must_exits
from app.services.outcome_tracking import trip_buy_journal
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


def opening_decision_for_trip(trip: RoundTrip) -> Optional[DecisionJournal]:
    """
    The opening decision of a round trip: its opening BUY journal, or that journal's
    parent if it is a top-up.

    A trip opened without a decision (a merger or spin-off handed over the shares, or a
    pre-#434 re-buy got no journal) has its first top-up saved as the opening instead,
    so that one is returned: the first parentless BUY decision made inside the trip.
    """
    journal = trip_buy_journal(trip)
    if journal is not None:
        return journal.parent_decision if journal.is_top_up else journal
    return _first_decision_made_in_trip(trip)


def _trip_transactions(trip: RoundTrip) -> list:
    """The trip's transactions in FIFO (date, id) order, opening to closing."""
    opening = trip.opening_transaction
    transactions = Transaction.query.filter_by(
        user_id=opening.user_id, company_id=opening.company_id,
    ).order_by(Transaction.date.asc(), Transaction.id.asc()).all()
    ids = [txn.id for txn in transactions]
    start = ids.index(opening.id)
    end = ids.index(trip.closing_transaction.id) + 1 if trip.closing_transaction else len(ids)
    return transactions[start:end]


def _first_decision_made_in_trip(trip: RoundTrip) -> Optional[DecisionJournal]:
    """
    The first parentless BUY decision whose own first transaction lies in the trip.
    The first-transaction check skips a pre-#434 journal that an earlier trip shares
    with this trip's top-ups.
    """
    transactions = _trip_transactions(trip)
    trip_ids = {txn.id for txn in transactions}
    for txn in transactions:
        journal = txn.decision_journal
        if txn.type != 'BUY' or journal is None or journal.decision_type != 'BUY' or journal.is_top_up:
            continue
        first = journal.transactions.order_by(Transaction.date.asc(), Transaction.id.asc()).first()
        if first is not None and first.id in trip_ids:
            return journal
    return None


def current_opening_decision(user_id: int, company_id: int) -> Optional[DecisionJournal]:
    """The opening decision of the company's latest round trip, or None (no trips, or none recorded)."""
    trips = get_round_trips(company_id, user_id)
    if not trips:
        return None
    return opening_decision_for_trip(trips[-1])


def current_thesis(user_id: int, company_id: int) -> Optional[ThesisEvolution]:
    """The company's current thesis version (highest version among is_current rows), or None."""
    return ThesisEvolution.query.filter_by(
        user_id=user_id, company_id=company_id, is_current=True,
    ).order_by(ThesisEvolution.version.desc(), ThesisEvolution.id.desc()).first()


def inherited_thesis(user_id: int, company_id: int, opening: Optional[DecisionJournal]) -> str:
    """
    The thesis a top-up copies: the current thesis version if it was written on or after
    the opening decision's date (or there is no opening decision), else the opening
    decision's own thesis. A re-buy writes no new version, so an older current version
    belongs to an earlier holding period. An empty choice falls back to the other one.
    """
    version = current_thesis(user_id, company_id)
    version_text = version.thesis if version is not None else None
    opening_text = opening.investment_thesis if opening is not None else None
    version_is_fresh = version is not None and (
        opening is None or version.created_at is None
        or ensure_timezone_aware(version.created_at).date() >= opening.decision_date)
    first, second = (version_text, opening_text) if version_is_fresh else (opening_text, version_text)
    for text in (first, second):
        if text and text.strip():
            return text
    return ''
