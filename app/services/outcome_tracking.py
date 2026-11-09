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
   trips (get_round_trips): open trips stay open, closed trips get exit data
4. Correlation analysis runs to identify patterns

Usage:
    from app.services.outcome_tracking import sync_outcomes_for_company

    sync_outcomes_for_company(user_id, company_id)  # flushes, never commits
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Set
import logging

from app import db
from app.utils.time_utils import date, days_between, now_utc
from app.models.ai_intelligence import ResearchOutcome
from app.models.checklist import DestinationCheckpoint
from app.models.journal import DecisionJournal
from app.models.portfolio import PortfolioPosition, Transaction, get_round_trips, update_portfolio_position_for_company
from app.models.research import ResearchProject
from .research_quality import calculate_research_quality

logger = logging.getLogger(__name__)

# Thesis text the bulk importer writes on its placeholder BUY journals.
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
        - Expected return vs actual (40%)
        - Hold period accuracy (30%)
        - Checkpoint hit rate (30%)
        """
        scores = []
        weights = []
        
        # 1. Return expectation accuracy (40%)
        if outcome.expected_return_pct is not None:
            expected = float(outcome.expected_return_pct)
            actual = realized_return
            
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
        outcomes = ResearchOutcome.query.filter(
            ResearchOutcome.user_id == user_id,
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
        
        # Calculate research correlation
        researched = [o for o in outcomes if o.research_quality_score is not None and o.research_quality_score > 0]
        unreasearched = [o for o in outcomes if o.research_quality_score is None or o.research_quality_score <= 0]
        scored = [o.research_quality_score for o in outcomes if o.research_quality_score is not None]
        
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


def is_placeholder_journal(journal: Optional[DecisionJournal]) -> bool:
    """True for the importer's made-up journal (thesis, confidence 5, expected return 15)."""
    return journal is not None and (journal.investment_thesis or '').strip() == IMPORTED_BUY_THESIS


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


def research_backed_company_ids(user_id: int) -> Set[int]:
    """Company ids whose latest trade outcome has a research project (#417 timing rule)."""
    latest = (
        db.session.query(ResearchOutcome.company_id, ResearchOutcome.project_id)
        .filter(ResearchOutcome.user_id == user_id)
        .distinct(ResearchOutcome.company_id)
        .order_by(ResearchOutcome.company_id, ResearchOutcome.decision_date.desc().nullslast(),
                  ResearchOutcome.id.desc())
        .all()
    )
    return {company_id for company_id, project_id in latest if project_id is not None}


def _apply_trip_to_outcome(outcome: ResearchOutcome, trip, user_id: int, company_id: int,
                           checkpoints: List[DestinationCheckpoint],
                           quality_cache: Dict[int, Any]) -> bool:
    """Write the trip onto the outcome. Returns True when any field actually changed."""
    tracker = OutcomeTracker()
    opening = trip.opening_transaction
    journal = opening.decision_journal
    if journal is not None and journal.decision_type != 'BUY':
        journal = None

    outcome.decision_date = trip.entry_date
    outcome.entry_price = trip.entry_price
    outcome.position_size = trip.buy_cost
    outcome.decision_journal_id = journal.id if journal else None

    real_journal = journal if journal is not None and not is_placeholder_journal(journal) else None
    outcome.initial_thesis = real_journal.investment_thesis_text if real_journal else None
    outcome.confidence_at_entry = real_journal.confidence_score if real_journal else None
    outcome.expected_return_pct = real_journal.expected_return if real_journal else None
    outcome.expected_hold_months = real_journal.expected_timeframe if real_journal else None

    # Known limitation: the quality score is the project's quality NOW, not on the
    # entry date, because nothing records past snapshots.
    project = research_project_for_trade(user_id, company_id, trip.entry_date, journal)
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
            if outcome.expected_return_pct is not None and realized is not None else None
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


def sync_outcomes_for_company(user_id: int, company_id: int) -> OutcomeSyncStats:
    """
    Make the company's ResearchOutcome rows match its round trips (one per trade).

    Rows are matched to trades by decision_date (in id order when several share a date)
    and updated in place so ids stay stable. Flushes, never commits; raises on error.
    """
    stats = OutcomeSyncStats()
    trips = get_round_trips(company_id, user_id)
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
class UserRebuildReport:
    user_id: int
    companies: int = 0
    created: int = 0
    updated: int = 0
    deleted: int = 0
    closed: int = 0
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
            report.created = report.updated = report.deleted = report.closed = 0
            report.positions_with_realized_pct = 0
            report.failed = True
            report.error = str(exc)
        reports.append(report)
    return reports
