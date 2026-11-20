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
parent_decision_id. Imported holding periods get one opening decision each
(ensure_import_decisions) and their later buys are linked to it, not given top-ups.
Nothing here commits except the one-off repair fix_imported_decisions; callers own
the transaction.

Stored shape (v1):
    {"version": 1, "captured_at": "<UTC ISO, Z>",
     "rules": [{"entry_id", "signal", "text", "created_at"}]}
Rows from before snapshots hold {"legacy_text": str}.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app import db
from app.models import DecisionJournal, ThesisEvolution, Transaction
from app.models.portfolio import RoundTrip, get_round_trips
from app.services.findings import active_must_exits
from app.services.outcome_tracking import IMPORTED_BUY_THESIS, sync_outcomes_for_company, trip_buy_journal
from app.utils.time_utils import datetime, ensure_timezone_aware, now_utc

logger = logging.getLogger(__name__)

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


def _buy_decisions_query(user_id: int, company_id: int):
    return DecisionJournal.query.filter(
        DecisionJournal.user_id == user_id,
        DecisionJournal.company_id == company_id,
        DecisionJournal.decision_type == 'BUY',
        DecisionJournal.is_portfolio_decision == True,  # noqa: E712
    )


def opening_buy_decision(user_id: int, company_id: int) -> Optional[DecisionJournal]:
    """The newest opening BUY for the company: the original thesis and expected return."""
    return _buy_decisions_query(user_id, company_id).filter(
        DecisionJournal.parent_decision_id.is_(None)
    ).order_by(DecisionJournal.decision_date.desc(), DecisionJournal.id.desc()).first()


def latest_buy_decision(user_id: int, company_id: int) -> Optional[DecisionJournal]:
    """The newest BUY for the company, top-ups included: the latest confidence."""
    return _buy_decisions_query(user_id, company_id).order_by(
        DecisionJournal.decision_date.desc(), DecisionJournal.id.desc()
    ).first()


@dataclass
class EnsureStats:
    created: int = 0  # opening decisions created
    linked: int = 0  # later buy rows linked to their opening decision


def _imported_opening_decision(trip: RoundTrip) -> DecisionJournal:
    """An honest opening decision for an imported trip: no confidence, return or timeframe."""
    opening = trip.opening_transaction
    journal = DecisionJournal(
        user_id=opening.user_id,
        company_id=opening.company_id,
        decision_type='BUY',
        decision_date=trip.entry_date,
        investment_thesis=IMPORTED_BUY_THESIS,
        is_portfolio_decision=True,
        is_imported=True,
        thesis_depth='minimal',
        non_research_source='other',
    )
    snapshot_exit_plan(journal)
    db.session.add(journal)
    opening.decision_journal = journal
    return journal


def ensure_import_decisions(user_id: int, company_id: int) -> EnsureStats:
    """
    Give each imported holding period one opening decision and link its later buys.

    A trip that already has an opening decision (on its opening row, or a manual one
    made on a later buy, as a backdated import leaves it) gets no new one; its unlinked
    BUYs, the opening row included, are linked to that decision, which is never edited.
    Only a trip with no decision at all, whose opening BUY was imported, gets an imported
    opening decision. Trips opened by a merger or spin-off are skipped, and a manual
    opening without a journal never gets an imported decision. Running it twice changes
    nothing. Flushes, never commits.
    """
    stats = EnsureStats()
    for trip in get_round_trips(company_id, user_id):
        if trip.opened_by_corporate_action:
            continue
        opening = trip.opening_transaction
        decision = opening_decision_for_trip(trip)
        created = None
        if decision is None:
            if opening.type != 'BUY' or not opening.is_imported:
                continue
            decision = created = _imported_opening_decision(trip)
            stats.created += 1
        for txn in trip.buys:
            # A just-created opening is linked through the relationship; its id lands at flush
            if (created is not None and txn is opening) or txn.decision_journal_id is not None:
                continue
            txn.decision_journal = decision
            stats.linked += 1
    db.session.flush()
    return stats


@dataclass
class ImportFixReport:
    user_id: int
    companies: int = 0
    created: int = 0
    linked: int = 0
    failed: bool = False
    error: Optional[str] = None


def fix_imported_decisions(user_id: Optional[int] = None, dry_run: bool = False) -> List[ImportFixReport]:
    """
    Run ensure_import_decisions, then the outcome sync, for every company with imported
    transactions. Commits per user (rolls back per user when dry_run). A failure rolls
    back that user only, is logged, and is recorded on the report.
    """
    query = db.session.query(Transaction.user_id, Transaction.company_id).filter(
        Transaction.is_imported.is_(True), Transaction.company_id.isnot(None))
    if user_id is not None:
        query = query.filter(Transaction.user_id == user_id)
    companies_by_user: Dict[int, List[int]] = {}
    for uid, company_id in sorted(query.distinct().all()):
        companies_by_user.setdefault(uid, []).append(company_id)

    reports: List[ImportFixReport] = []
    for uid, company_ids in sorted(companies_by_user.items()):
        report = ImportFixReport(user_id=uid)
        try:
            report.companies = len(company_ids)
            for company_id in company_ids:
                stats = ensure_import_decisions(uid, company_id)
                report.created += stats.created
                report.linked += stats.linked
                sync_outcomes_for_company(uid, company_id)
            if dry_run:
                db.session.rollback()
            else:
                db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.error(f"Imported-decision fix failed for user {uid}", exc_info=True)
            # Nothing landed for this user, so don't let the totals count it
            report.created = report.linked = 0
            report.failed = True
            report.error = str(exc)
        reports.append(report)
    return reports
