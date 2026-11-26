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
Outcome Tracking Service

Links research quality to investment outcomes.
This is the core feedback loop that enables learning from investment results.

Lifecycle:
1. User completes research (ResearchSession or ResearchProject)
2. Every write to a company's transactions (add, edit, delete, sync-positions,
   bulk import) calls sync_outcomes_for_company(user_id, company_id)
3. The sync rebuilds that company's ResearchOutcome rows from its FIFO round
   trips (get_round_trips): open trips stay open, closed trips get exit data.
   Trips a merger or spin-off opened get an outcome flagged is_received, with no
   research or expectation fields. First it re-links the BUY decisions
   (relink_trip_decisions), so each trip keeps one opening decision when a
   backdated, edited or deleted transaction merges or splits holding periods
4. Correlation analysis runs to identify patterns

Usage:
    from app.services.outcome_tracking import sync_outcomes_for_company

    sync_outcomes_for_company(user_id, company_id)  # flushes, never commits
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import logging
from uuid import uuid4

from app import cache, db
from app.utils.financial_utils import calculate_cagr
from app.utils.time_utils import date, days_between, now_utc
from app.models.ai_intelligence import ResearchOutcome
from app.models.checklist import DestinationCheckpoint
from app.models.journal import DecisionJournal
from app.models.portfolio import (
    PortfolioPosition, RECEIVED_POSITION_TYPES, RoundTrip, Transaction, find_sale, get_round_trips,
    update_portfolio_position_for_company,
)
from app.models.research import ResearchProject
from .research_quality import calculate_research_quality

logger = logging.getLogger(__name__)

# Thesis label the bulk importer writes on its opening BUY decisions. A label only:
# imports are recognised by is_imported, never by this text.
IMPORTED_BUY_THESIS = 'Imported via bulk uploader'


class OutcomeTracker:
    """
    Tracks and correlates research quality with investment outcomes.
    
    This is the core service for the Phase 1 feedback loop:
    Research → Decision → Transaction → Outcome → Learning
    """
    
    # Outcome categories based on return percentage
    OUTCOME_THRESHOLDS = {
        'big_win': 25,      # >= 25% return
        'small_win': 5,     # >= 5% return
        'break_even': -5,   # >= -5% return
        'small_loss': -25,  # >= -25% return
        'big_loss': float('-inf')  # < -25% return
    }
    
    def _calculate_thesis_accuracy(
        self,
        outcome: ResearchOutcome,
        realized_return: float
    ) -> float:
        """
        Calculate how accurate the initial thesis was.
        
        Based on:
        - Expected CAGR vs realized CAGR (40%)
        - Hold period accuracy (30%)
        - Checkpoint hit rate (30%)
        """
        scores = []
        weights = []
        
        # 1. Return expectation accuracy (40%): both sides as annual rates
        if outcome.expected_cagr_pct is not None:
            expected = float(outcome.expected_cagr_pct)
            actual = calculate_cagr(realized_return, outcome.actual_hold_days or 0)
            
            # Same direction = partial credit
            if (expected > 0 and actual > 0) or (expected < 0 and actual < 0):
                # Score based on how close
                diff = abs(expected - actual)
                accuracy = max(0, 100 - diff * 2)  # -2 points per % difference
                scores.append(accuracy)
            else:
                # Wrong direction
                scores.append(20)
            weights.append(0.4)
        
        # 2. Hold period accuracy (30%)
        if outcome.expected_hold_months and outcome.actual_hold_days:
            expected_days = outcome.expected_hold_months * 30
            actual_days = outcome.actual_hold_days
            
            ratio = min(expected_days, actual_days) / max(expected_days, actual_days)
            scores.append(ratio * 100)
            weights.append(0.3)
        
        # 3. Checkpoint accuracy (30%)
        if outcome.checkpoints_total and outcome.checkpoints_total > 0:
            checkpoint_pct = (outcome.checkpoints_met or 0) / outcome.checkpoints_total
            scores.append(checkpoint_pct * 100)
            weights.append(0.3)
        
        # Calculate weighted average
        if scores:
            total_weight = sum(weights)
            weighted_sum = sum(s * w for s, w in zip(scores, weights))
            return weighted_sum / total_weight
        
        return 50.0  # Default neutral score
    
    def _categorize_outcome(self, return_pct: float) -> str:
        """Categorize outcome based on return percentage"""
        if return_pct >= self.OUTCOME_THRESHOLDS['big_win']:
            return 'big_win'
        elif return_pct >= self.OUTCOME_THRESHOLDS['small_win']:
            return 'small_win'
        elif return_pct >= self.OUTCOME_THRESHOLDS['break_even']:
            return 'break_even'
        elif return_pct >= self.OUTCOME_THRESHOLDS['small_loss']:
            return 'small_loss'
        else:
            return 'big_loss'
    
    def get_user_outcome_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Get summary statistics for a user's outcomes.
        
        Returns:
            Dict with stats like win_rate, avg_return, etc.
        """
        outcomes = portfolio_outcomes(user_id).filter(
            ResearchOutcome.realized_return_pct.isnot(None)
        ).all()
        
        if not outcomes:
            return {
                'total_investments': 0,
                'win_rate': None,
                'avg_return': None,
                'research_correlation': None
            }
        
        wins = [o for o in outcomes if o.realized_return_pct > 0]
        
        # Research correlation is about decisions: received holdings (#451) have none
        decided = [o for o in outcomes if not o.is_received]
        researched = [o for o in decided if o.research_quality_score is not None and o.research_quality_score > 0]
        unreasearched = [o for o in decided if o.research_quality_score is None or o.research_quality_score <= 0]
        scored = [o.research_quality_score for o in decided if o.research_quality_score is not None]
        
        research_advantage = None
        if researched and unreasearched:
            researched_avg = sum(o.realized_return_pct for o in researched) / len(researched)
            unreasearched_avg = sum(o.realized_return_pct for o in unreasearched) / len(unreasearched)
            research_advantage = researched_avg - unreasearched_avg
        
        return {
            'total_investments': len(outcomes),
            'win_rate': len(wins) / len(outcomes) * 100,
            'avg_return': sum(o.realized_return_pct for o in outcomes) / len(outcomes),
            'best_return': max(o.realized_return_pct for o in outcomes),
            'worst_return': min(o.realized_return_pct for o in outcomes),
            'avg_hold_days': sum(o.actual_hold_days or 0 for o in outcomes) / len(outcomes),
            'research_advantage_pct': research_advantage,
            'avg_research_quality': sum(scored) / len(scored) if scored else None,
            'outcome_breakdown': {
                'big_wins': len([o for o in outcomes if o.outcome_category == 'big_win']),
                'small_wins': len([o for o in outcomes if o.outcome_category == 'small_win']),
                'break_even': len([o for o in outcomes if o.outcome_category == 'break_even']),
                'small_losses': len([o for o in outcomes if o.outcome_category == 'small_loss']),
                'big_losses': len([o for o in outcomes if o.outcome_category == 'big_loss']),
            }
        }


def get_outcome_stats(user_id: int) -> Dict[str, Any]:
    """
    Get outcome statistics for a user.
    
    Convenience function for dashboards and analytics.
    """
    tracker = OutcomeTracker()
    return tracker.get_user_outcome_stats(user_id)


# ============================================================
# Rebuild outcomes from round trips (#417)
# ============================================================

@dataclass
class OutcomeSyncStats:
    created: int = 0
    updated: int = 0
    deleted: int = 0
    closed: int = 0  # outcomes that are closed after the sync
    relinked: int = 0  # BUY decisions whose parent_decision_id changed


def is_placeholder_journal(journal: Optional[DecisionJournal]) -> bool:
    """True for a decision the importer made: it carries no thesis, confidence or expectations."""
    return journal is not None and journal.is_imported


def research_project_for_trade(
    user_id: int,
    company_id: int,
    entry_date: date,
    journal: Optional[DecisionJournal],
) -> Optional[ResearchProject]:
    """
    The research project that counts for a trade entered on entry_date.

    An explicit journal link wins (it was made when the user bought). Otherwise the
    user's project for the company counts if it was created on or before entry_date,
    whatever its status. Research created later never counts for this trade.
    """
    if journal is not None and journal.linked_research_id:
        project = db.session.get(ResearchProject, journal.linked_research_id)
        if project is not None:
            return project
    project = ResearchProject.query.filter_by(user_id=user_id, company_id=company_id).first()
    if project is not None and project.created_at and project.created_at.date() <= entry_date:
        return project
    return None


def portfolio_outcomes(user_id: int):
    """Every trade outcome, received included: for portfolio stats."""
    return ResearchOutcome.query.filter(ResearchOutcome.user_id == user_id)


def decision_outcomes(user_id: int):
    """Outcomes with a research decision (not received): for research and decision analytics."""
    return portfolio_outcomes(user_id).filter(ResearchOutcome.is_received.is_(False))


def trip_buy_journal(trip: RoundTrip) -> Optional[DecisionJournal]:
    """The BUY journal of the transaction that opened the trade, or None."""
    journal = trip.opening_transaction.decision_journal
    if journal is not None and journal.decision_type != 'BUY':
        return None
    return journal


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


def _orphan_buy_decisions(user_id: int, company_id: int) -> List[DecisionJournal]:
    """Portfolio BUY decisions with no transactions left (their buys were deleted), oldest first."""
    linked = db.session.query(Transaction.id).filter(Transaction.decision_journal_id == DecisionJournal.id)
    return DecisionJournal.query.filter(
        DecisionJournal.user_id == user_id,
        DecisionJournal.company_id == company_id,
        DecisionJournal.decision_type == 'BUY',
        DecisionJournal.is_portfolio_decision.is_(True),
        ~linked.exists(),
    ).order_by(DecisionJournal.decision_date, DecisionJournal.id).all()


def relink_trip_decisions(trips: List[RoundTrip]) -> int:
    """
    Give each round trip exactly one opening decision (#448): the earliest BUY decision
    made in the trip loses its parent, and the trip's later BUY decisions point at it.
    Run whenever round trips can change, since a backdated, edited or deleted
    transaction can merge two holding periods or split one.

    A decision belongs to the trip of its first BUY row, so a pre-#434 journal that is
    also on a later trip's buys stays with its own trip. A trip whose opening row
    carries an earlier trip's decision (a split imported period) keeps that decision as
    its opening, as opening_decision_for_trip reads it, so its own decisions point
    there. A decision whose buys were all deleted is never an opening: it points at the
    opening of the first trip that ends on or after its date (else the last trip).

    Only parent_decision_id changes, never the decision's reasoning or which
    transactions it is on. Returns how many decisions changed. Flushes when something
    changed.
    """
    if not trips:
        return 0
    first = trips[0].opening_transaction
    journals: Dict[int, DecisionJournal] = {}  # every decision on a trip's BUY rows, by id
    wanted: Dict[int, Optional[int]] = {}  # decision id -> its parent_decision_id after the relink
    trip_openings: List[Optional[int]] = []
    for trip in trips:
        opening_row = trip.opening_transaction.decision_journal
        inherited = (opening_row is not None and opening_row.decision_type == 'BUY'
                     and opening_row.id in journals)
        decisions = []
        for txn in trip.buys:
            journal = txn.decision_journal
            if journal is None or journal.decision_type != 'BUY' or journal.id in journals:
                continue
            journals[journal.id] = journal
            decisions.append(journal)
        if inherited:
            # The opening row's decision (or its parent, if a top-up) is this trip's opening
            parent_id = wanted.get(opening_row.id, opening_row.parent_decision_id)
            opening_id = parent_id if parent_id is not None else opening_row.id
        elif decisions:
            opening_id = decisions.pop(0).id
            wanted[opening_id] = None
        else:
            opening_id = None
        for journal in decisions:
            wanted[journal.id] = opening_id
        trip_openings.append(opening_id)

    for orphan in _orphan_buy_decisions(first.user_id, first.company_id):
        index = next((i for i, trip in enumerate(trips)
                      if trip.exit_date is None or trip.exit_date >= orphan.decision_date), len(trips) - 1)
        if trip_openings[index] is not None:
            journals[orphan.id] = orphan
            wanted[orphan.id] = trip_openings[index]

    touched = set(journals)
    changed = 0
    for journal_id, parent_id in wanted.items():
        journal = journals[journal_id]
        if journal.parent_decision_id != parent_id:
            touched.add(journal.parent_decision_id)
            # The column, not the relationship: swapping two decisions' roles would be
            # a circular dependency for the unit of work
            journal.parent_decision_id = parent_id
            changed += 1
    if changed:
        db.session.flush()
        # Old parents too, so their top_ups don't list the moved decisions
        for obj in list(db.session.identity_map.values()):
            if isinstance(obj, DecisionJournal) and obj.id in touched:
                db.session.expire(obj, ['parent_decision', 'top_ups'])
    return changed


def _apply_trip_to_outcome(outcome: ResearchOutcome, trip, user_id: int, company_id: int,
                           checkpoints: List[DestinationCheckpoint],
                           quality_cache: Dict[int, Any]) -> bool:
    """Write the trip onto the outcome. Returns True when any field actually changed."""
    tracker = OutcomeTracker()
    # The holding period's opening decision, even when a top-up's row now opens the trip
    journal = opening_decision_for_trip(trip)

    outcome.decision_date = trip.entry_date
    outcome.entry_price = trip.entry_price
    outcome.position_size = trip.buy_cost
    outcome.decision_journal_id = journal.id if journal else None
    outcome.is_received = bool(trip.opened_by_corporate_action)

    # Received shares carry no research decision: no journal fields, no research project
    real_journal = (journal if journal is not None and not is_placeholder_journal(journal)
                    and not outcome.is_received else None)
    outcome.initial_thesis = real_journal.investment_thesis_text if real_journal else None
    outcome.confidence_at_entry = real_journal.confidence_score if real_journal else None
    outcome.expected_cagr_pct = real_journal.expected_cagr if real_journal else None
    outcome.expected_hold_months = real_journal.expected_timeframe if real_journal else None

    # Known limitation: the quality score is the project's quality NOW, not on the
    # entry date, because nothing records past snapshots.
    project = (None if outcome.is_received
               else research_project_for_trade(user_id, company_id, trip.entry_date, journal))
    quality = None
    if project:
        if project.id not in quality_cache:
            quality_cache[project.id] = calculate_research_quality(research_project_id=project.id)
        quality = quality_cache[project.id]
    outcome.project_id = project.id if project else None
    outcome.research_quality_score = quality.overall_score if quality else None
    outcome.questions_answered = quality.questions_answered if quality else 0
    outcome.questions_total = quality.questions_total if quality else 0
    outcome.documents_analyzed = quality.documents_analyzed if quality else 0
    outcome.research_duration_minutes = quality.research_duration_minutes if quality else 0
    outcome.checklist_completion_pct = (
        quality.questions_answered / quality.questions_total * 100
        if quality and quality.questions_total > 0 else 0
    )
    outcome.had_financial_analysis = quality.had_financial_analysis if quality else False
    outcome.had_competitive_analysis = quality.had_competitive_analysis if quality else False
    outcome.had_management_review = quality.had_management_review if quality else False
    outcome.had_valuation_model = quality.had_valuation_model if quality else False

    outcome.checkpoints_total = len(checkpoints)
    outcome.checkpoints_met = len([c for c in checkpoints if c.status == 'Met'])

    if trip.is_closed:
        realized = trip.realized_return_pct
        was_closed = outcome.exit_date is not None and outcome.outcome_recorded_at is not None
        outcome.exit_date = trip.exit_date
        outcome.exit_price = trip.exit_price
        outcome.realized_return_pct = realized
        outcome.actual_hold_days = days_between(trip.entry_date, trip.exit_date)
        outcome.outcome_category = tracker._categorize_outcome(realized) if realized is not None else None
        if not was_closed:
            outcome.outcome_recorded_at = now_utc()
        outcome.thesis_accuracy_score = (
            tracker._calculate_thesis_accuracy(outcome, realized)
            if outcome.expected_cagr_pct is not None and realized is not None else None
        )
    else:
        outcome.exit_date = None
        outcome.exit_price = None
        outcome.realized_return_pct = None
        outcome.actual_hold_days = None
        outcome.outcome_category = None
        outcome.outcome_recorded_at = None
        outcome.thesis_accuracy_score = None
    changed = db.session.is_modified(outcome)
    if changed:
        outcome.last_updated_at = now_utc()
    return changed


INSIGHTS_VERSION_KEY = 'insights-version:{user_id}'


def bump_insights_version(user_id: int) -> None:
    """Give the user's cached learning insights a new cache key (see get_learning_insights)."""
    cache.set(INSIGHTS_VERSION_KEY.format(user_id=user_id), uuid4().hex, timeout=0)


def sync_outcomes_for_company(user_id: int, company_id: int) -> OutcomeSyncStats:
    """
    Make the company's ResearchOutcome rows match its round trips (one per trade),
    after re-linking the trips' BUY decisions (relink_trip_decisions).

    Rows are matched to trades by decision_date (in id order when several share a date)
    and updated in place so ids stay stable. Flushes, never commits; raises on error.
    """
    stats = OutcomeSyncStats()
    trips = get_round_trips(company_id, user_id)
    stats.relinked = relink_trip_decisions(trips)
    existing = ResearchOutcome.query.filter_by(user_id=user_id, company_id=company_id) \
        .order_by(ResearchOutcome.id).all()
    by_date: Dict[Any, List[ResearchOutcome]] = {}
    for row in existing:
        by_date.setdefault(row.decision_date, []).append(row)

    checkpoints = DestinationCheckpoint.query.filter_by(company_id=company_id, user_id=user_id).all()

    quality_cache: Dict[int, Any] = {}
    kept: List[ResearchOutcome] = []
    for trip in trips:
        candidates = by_date.get(trip.entry_date)
        if candidates:
            outcome = candidates.pop(0)
            if _apply_trip_to_outcome(outcome, trip, user_id, company_id, checkpoints, quality_cache):
                stats.updated += 1
        else:
            outcome = ResearchOutcome(user_id=user_id, company_id=company_id,
                                      thesis_still_valid=True, created_at=now_utc())
            db.session.add(outcome)
            stats.created += 1
            _apply_trip_to_outcome(outcome, trip, user_id, company_id, checkpoints, quality_cache)
        kept.append(outcome)

    for leftovers in by_date.values():
        for row in leftovers:
            db.session.delete(row)
            stats.deleted += 1

    stats.closed = len([o for o in kept if o.exit_date is not None])
    db.session.flush()
    bump_insights_version(user_id)
    return stats


def safe_sync_outcomes(user_id: int, company_id: int) -> Optional[OutcomeSyncStats]:
    """
    Run sync_outcomes_for_company inside a savepoint. A failure rolls back only the
    sync's own writes, is logged with a traceback, and returns None, so the caller's
    transaction write is never lost.
    """
    try:
        with db.session.begin_nested():
            return sync_outcomes_for_company(user_id, company_id)
    except Exception:
        logger.warning(f"[AI] Outcome sync failed for company {company_id}", exc_info=True)
        return None


@dataclass
class SalePostmortem:
    """What the sell post-mortem shows for one SELL journal."""
    sell_transaction: Optional[Transaction] = None
    buy_journal: Optional[DecisionJournal] = None
    calculated_return: Optional[float] = None
    closed_trade: bool = False  # True when this sale took the holding to 0 shares


def sale_postmortem(sell_journal: DecisionJournal) -> SalePostmortem:
    """
    The return and BUY journal for the trade a SELL journal's sale belongs to.

    A sale that closed the trade gets the trade's realized return (the value the
    trade's ResearchOutcome holds); a partial sale gets the return on the shares it
    sold. A journal with no linked SELL transaction gets an empty result.
    """
    txn = Transaction.query.filter_by(
        user_id=sell_journal.user_id,
        company_id=sell_journal.company_id,
        decision_journal_id=sell_journal.id,
        type='SELL',
    ).order_by(Transaction.id.desc()).first()
    if txn is None:
        return SalePostmortem()

    match = find_sale(txn)
    if match is None:
        return SalePostmortem(sell_transaction=txn)  # sold nothing the FIFO walk held

    trip, sale = match
    closed = trip.closing_transaction is not None and trip.closing_transaction.id == txn.id
    return SalePostmortem(
        sell_transaction=txn,
        buy_journal=trip_buy_journal(trip),
        calculated_return=trip.realized_return_pct if closed else sale.return_pct,
        closed_trade=closed,
    )


@dataclass
class UserRebuildReport:
    user_id: int
    companies: int = 0
    created: int = 0
    updated: int = 0
    deleted: int = 0
    closed: int = 0
    relinked: int = 0
    positions_with_realized_pct: int = 0
    failed: bool = False
    error: Optional[str] = None


def rebuild_trade_outcomes(user_id: Optional[int] = None, dry_run: bool = False) -> List[UserRebuildReport]:
    """
    Backfill positions' realized_gain_loss_pct and ResearchOutcome rows from existing
    transaction history. Commits per user (rolls back per user when dry_run). A failure
    rolls back that user only, is logged, and is recorded on the report.
    """
    txn_query = db.session.query(Transaction.user_id, Transaction.company_id).filter(
        Transaction.company_id.isnot(None))
    outcome_query = db.session.query(ResearchOutcome.user_id, ResearchOutcome.company_id)
    if user_id is not None:
        txn_query = txn_query.filter(Transaction.user_id == user_id)
        outcome_query = outcome_query.filter(ResearchOutcome.user_id == user_id)
    # Pairs with outcomes but no transactions are included so leftovers get deleted
    pairs = {(row[0], row[1]) for row in txn_query.distinct().all()}
    pairs |= {(row[0], row[1]) for row in outcome_query.distinct().all()}
    companies_by_user: Dict[int, List[int]] = {}
    for uid, company_id in sorted(pairs):
        companies_by_user.setdefault(uid, []).append(company_id)

    reports: List[UserRebuildReport] = []
    for uid, company_ids in sorted(companies_by_user.items()):
        report = UserRebuildReport(user_id=uid)
        try:
            report.companies = len(company_ids)
            for company_id in company_ids:
                update_portfolio_position_for_company(company_id, uid)
                stats = sync_outcomes_for_company(uid, company_id)
                report.created += stats.created
                report.updated += stats.updated
                report.deleted += stats.deleted
                report.closed += stats.closed
                report.relinked += stats.relinked
            report.positions_with_realized_pct = PortfolioPosition.query.filter(
                PortfolioPosition.user_id == uid,
                PortfolioPosition.realized_gain_loss_pct.isnot(None),
            ).count()
            if dry_run:
                db.session.rollback()
            else:
                db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.error(f"Outcome rebuild failed for user {uid}", exc_info=True)
            # Nothing landed for this user, so don't let the totals count it
            report.created = report.updated = report.deleted = report.closed = report.relinked = 0
            report.positions_with_realized_pct = 0
            report.failed = True
            report.error = str(exc)
        reports.append(report)
    return reports


@dataclass
class ReceivedBackfillReport:
    user_id: int
    companies: int = 0
    created: int = 0
    updated: int = 0
    deleted: int = 0
    failed: bool = False
    error: Optional[str] = None


def backfill_received_outcomes(user_id: Optional[int] = None, dry_run: bool = False) -> List[ReceivedBackfillReport]:
    """
    Create the missing is_received outcomes for holdings opened by a merger or spin-off (#451).
    Covers every (user, company) pair with a received transaction, which is a superset of the
    companies with a received round trip; re-syncing the others is harmless. Commits per user
    (rolls back per user when dry_run). A failure rolls back that user only, is logged, and is
    recorded on the report.
    """
    query = db.session.query(Transaction.user_id, Transaction.company_id).filter(
        Transaction.company_id.isnot(None),
        Transaction.type.in_(RECEIVED_POSITION_TYPES))
    if user_id is not None:
        query = query.filter(Transaction.user_id == user_id)
    companies_by_user: Dict[int, List[int]] = {}
    for uid, company_id in sorted({(row[0], row[1]) for row in query.distinct().all()}):
        companies_by_user.setdefault(uid, []).append(company_id)

    reports: List[ReceivedBackfillReport] = []
    for uid, company_ids in sorted(companies_by_user.items()):
        report = ReceivedBackfillReport(user_id=uid)
        try:
            report.companies = len(company_ids)
            for company_id in company_ids:
                stats = sync_outcomes_for_company(uid, company_id)
                report.created += stats.created
                report.updated += stats.updated
                report.deleted += stats.deleted
            if dry_run:
                db.session.rollback()
            else:
                db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.error(f"Received-outcome backfill failed for user {uid}", exc_info=True)
            report.created = report.updated = report.deleted = 0
            report.failed = True
            report.error = str(exc)
        reports.append(report)
    return reports
