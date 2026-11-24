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
Portfolio Intelligence Service

Provides insights and analytics on portfolio performance,
correlating research quality with investment outcomes.

This is the "learning layer" that helps investors understand:
- Does better research lead to better returns?
- What patterns exist in their winning/losing trades?
- Are they improving over time?

Usage:
    from app.services.portfolio_intelligence import PortfolioIntelligenceService
    
    service = PortfolioIntelligenceService(user_id=123)
    checkpoints = service.get_upcoming_checkpoints()
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
import logging

from sqlalchemy.orm import joinedload

from app import cache
from app.utils.time_utils import days_between, now_utc
from app.utils.financial_utils import calculate_cagr

from app.models import DecisionJournal, PortfolioPosition, DestinationCheckpoint, Company, ThesisEvolution
from app.services.decision_journals import opening_buy_decision
# Below MIN_DAYS_FOR_ANNUALIZED_COMPARISON days held, total return is compared with
# the return the expected CAGR implies by now
from app.services.position_returns import MIN_DAYS_FOR_ANNUALIZED_COMPARISON, position_returns

logger = logging.getLogger(__name__)

# Thresholds for outcome analysis (days)
SHORT_HOLD_THRESHOLD_DAYS = 90
DAYS_PER_YEAR = 365


def expected_return_to_date(expected_cagr: float, days_held: int) -> float:
    """Total return % a position compounding at expected_cagr should have after days_held."""
    growth = max(1 + float(expected_cagr) / 100, 0.0)
    return (growth ** (days_held / DAYS_PER_YEAR) - 1) * 100


@dataclass
class ReturnComparison:
    """A position's return next to its expected CAGR, both on the same basis."""
    actual: float
    expected: float
    annualized: bool  # False for short holds, where both are totals to date


def compare_to_expected_cagr(
    expected_cagr: float,
    total_return: float,
    days_held: int,
    annualized_return: Optional[float] = None
) -> ReturnComparison:
    """Put a position's return and its expected CAGR on the same basis.

    Below MIN_DAYS_FOR_ANNUALIZED_COMPARISON days, annualizing would blow a small
    move up, so the total return is set against what the expected CAGR implies
    by now. After that the position's CAGR is set against the expected CAGR.
    """
    if days_held < MIN_DAYS_FOR_ANNUALIZED_COMPARISON:
        return ReturnComparison(float(total_return),
                                expected_return_to_date(expected_cagr, days_held), False)
    if annualized_return is None:
        annualized_return = calculate_cagr(total_return, days_held)
    return ReturnComparison(float(annualized_return), float(expected_cagr), True)


@dataclass
class CheckpointReminder:
    """A checkpoint reminder for display"""
    id: int
    company_name: str
    company_ticker: str
    company_id: int
    metric: str            # E.g., "Quarterly Revenue", "EPS"
    expectation: str       # E.g., ">$5 Billion", "Beat estimates"
    description: str
    target_date: date
    status: str  # 'overdue', 'this_week', 'upcoming'
    days_until: int  # negative if overdue
    checkpoint_type: Optional[str]
    metric_target: Optional[str]


@dataclass
class ReturnTarget:
    """The expected return a position is measured against."""
    expected_cagr: Optional[float]  # Annual return % (CAGR) expected from purchase
    expected_timeframe_months: Optional[int]  # Holding period the CAGR is expected over
    source: Optional[str]  # 'thesis' (revised in a thesis version), 'purchase', or None
    thesis_version: Optional[int]  # Version that set it, when source == 'thesis'


NO_RETURN_TARGET = ReturnTarget(None, None, None, None)


def _resolve_return_target(journal, theses) -> ReturnTarget:
    """Latest thesis version that sets a return target, else the BUY decision's.

    ``theses`` are the company's thesis versions, newest first.
    """
    for thesis in theses:
        if thesis.expected_cagr is not None:
            return ReturnTarget(thesis.expected_cagr, thesis.expected_timeframe,
                                'thesis', thesis.version)
    if journal is not None and journal.expected_cagr is not None:
        return ReturnTarget(journal.expected_cagr, journal.expected_timeframe,
                            'purchase', None)
    return NO_RETURN_TARGET


@dataclass
class ThesisReality:
    """Comparison of thesis expectations vs actual performance"""
    company_name: str
    company_ticker: str
    company_id: int
    position_id: int

    # Original thesis
    investment_thesis: str
    expected_cagr: Optional[float]  # Annual return % (CAGR) expected
    expected_timeframe_months: Optional[int]  # Holding period the CAGR is expected over
    target_source: Optional[str]  # 'thesis', 'purchase', or None (no target)
    target_version: Optional[int]  # Thesis version that set the target
    confidence_score: Optional[int]

    # Reality
    actual_return_pct: float
    annualized_return_pct: float  # CAGR - Compound Annual Growth Rate
    days_held: int
    current_price: Optional[Decimal]

    # Assessment
    status: str  # 'on_track', 'exceeding', 'behind', 'needs_attention'
    thesis_still_valid: Optional[bool]


@dataclass
class LearningInsight:
    """A learning insight derived from user's data"""
    category: str  # 'winning_pattern', 'warning', 'edge', 'improvement'
    title: str
    description: str
    supporting_data: Optional[str]
    importance: str  # 'high', 'medium', 'low'
    key: str = ''


def outcome_hold_days(outcome) -> Optional[int]:
    """Days the trade was held: the stored value, else derived from the dates."""
    if outcome.actual_hold_days is not None:
        return outcome.actual_hold_days
    if outcome.decision_date and outcome.exit_date:
        return days_between(outcome.decision_date, outcome.exit_date)
    return None


class PortfolioIntelligenceService:
    """
    Main service for portfolio intelligence and learning insights.
    """

    def __init__(self, user_id: int):
        self.user_id = user_id
    
    # =========================================================================
    # STEP 2: Checkpoint Reminders
    # =========================================================================
    
    def get_upcoming_checkpoints(self, days_ahead: int = 30) -> Dict[str, List[CheckpointReminder]]:
        """
        Get upcoming and overdue checkpoints grouped by urgency.
        
        Args:
            days_ahead: How many days ahead to look
            
        Returns:
            Dict with keys 'overdue', 'this_week', 'upcoming'
        """
        today = now_utc().date()
        week_from_now = today + timedelta(days=7)
        month_from_now = today + timedelta(days=30)
        three_months_from_now = today + timedelta(days=90)

        # Get active checkpoints for companies in portfolio
        from sqlalchemy import select
        portfolio_company_ids_query = select(PortfolioPosition.company_id).filter(
            PortfolioPosition.user_id == self.user_id,
            PortfolioPosition.is_active == True
        ).scalar_subquery()

        # Get ALL active checkpoints with eager-loaded company (avoid N+1)
        checkpoints = DestinationCheckpoint.query.filter(
            DestinationCheckpoint.user_id == self.user_id,
            DestinationCheckpoint.company_id.in_(portfolio_company_ids_query),
            DestinationCheckpoint.status == 'Active'
        ).options(
            joinedload(DestinationCheckpoint.company)
        ).order_by(DestinationCheckpoint.target_date.asc()).all()

        result = {
            'overdue': [],
            'this_week': [],
            'this_month': [],
            'next_3_months': [],
            'beyond': []
        }

        for cp in checkpoints:
            days_until = (cp.target_date - today).days

            if days_until < 0:
                status = 'overdue'
            elif days_until <= 7:
                status = 'this_week'
            elif days_until <= 30:
                status = 'this_month'
            elif days_until <= 90:
                status = 'next_3_months'
            else:
                status = 'beyond'
            
            reminder = CheckpointReminder(
                id=cp.id,
                company_name=cp.company.name if cp.company else 'Unknown',
                company_ticker=cp.company.ticker_symbol if cp.company else '???',
                company_id=cp.company_id,
                description='',  # DestinationCheckpoint doesn't have description field
                target_date=cp.target_date,
                metric=cp.metric or '',
                expectation=cp.expectation or '',
                status=status,
                days_until=days_until,
                checkpoint_type=cp.checkpoint_type if hasattr(cp, 'checkpoint_type') else None,
                metric_target=cp.metric_target if hasattr(cp, 'metric_target') else None
            )
            
            result[status].append(reminder)
        
        return result
    
    def get_checkpoint_summary(self) -> Dict[str, Any]:
        """Get a quick summary of checkpoint status"""
        checkpoints = self.get_upcoming_checkpoints()

        return {
            'overdue_count': len(checkpoints['overdue']),
            'this_week_count': len(checkpoints['this_week']),
            'this_month_count': len(checkpoints['this_month']),
            'next_3_months_count': len(checkpoints['next_3_months']),
            'beyond_count': len(checkpoints['beyond']),
            'total_active': sum(len(v) for v in checkpoints.values()),
            'needs_attention': len(checkpoints['overdue']) > 0
        }
    
    # =========================================================================
    # STEP 3: Position Monitoring (Thesis vs Reality)
    # =========================================================================
    
    def get_thesis_reality_check(self) -> List[ThesisReality]:
        """
        Compare original investment thesis to actual performance.
        Uses the position's annualized return (XIRR over its own cash flows, so
        realized gains and dividends count) for a fair comparison across
        holding periods.

        Returns:
            List of ThesisReality for each active position
        """
        # Get active positions with eager-loaded company+sector
        positions = PortfolioPosition.query.filter_by(
            user_id=self.user_id,
            is_active=True
        ).options(
            joinedload(PortfolioPosition.company).joinedload(Company.sector)
        ).all()

        if not positions:
            return []

        # Batch load all BUY decision journals for these companies (avoids N+1)
        company_ids = [p.company_id for p in positions]
        all_journals = DecisionJournal.query.filter(
            DecisionJournal.user_id == self.user_id,
            DecisionJournal.company_id.in_(company_ids),
            DecisionJournal.decision_type == 'BUY',
            DecisionJournal.is_portfolio_decision == True,
            DecisionJournal.parent_decision_id.is_(None)
        ).order_by(DecisionJournal.decision_date.desc(), DecisionJournal.id.desc()).all()
        # Keep the most recent opening decision per company (top-ups don't restate the thesis)
        journals_map = {}
        for j in all_journals:
            if j.company_id not in journals_map:
                journals_map[j.company_id] = j

        # Thesis versions can revise the return target set at purchase
        theses_map = {}
        for t in ThesisEvolution.query.filter(
            ThesisEvolution.user_id == self.user_id,
            ThesisEvolution.company_id.in_(company_ids)
        ).order_by(ThesisEvolution.version.desc()).all():
            theses_map.setdefault(t.company_id, []).append(t)

        # Lifetime returns: realized gains and dividends count, not only the open shares
        returns = position_returns(positions)

        results = []

        for position in positions:
            journal = journals_map.get(position.company_id)
            target = _resolve_return_target(journal, theses_map.get(position.company_id, []))

            # Calculate actual returns (a position with no price yet reads as flat)
            measured = returns.get(position.company_id)
            actual_return = measured.total_return_pct if measured else 0.0
            days_held = position.days_held or 0
            annualized_return = (measured.annualized_pct if measured and measured.annualized_pct is not None
                                 else calculate_cagr(actual_return, days_held))

            # Determine status (using annualized return for fair comparison)
            status = self._assess_thesis_status(
                expected_cagr=target.expected_cagr,
                annualized_return=annualized_return,
                total_return=actual_return,
                days_held=days_held
            )

            results.append(ThesisReality(
                company_name=position.company.name if position.company else 'Unknown',
                company_ticker=position.company.ticker_symbol if position.company else '???',
                company_id=position.company_id,
                position_id=position.id,
                investment_thesis=journal.investment_thesis if journal else 'No thesis recorded',
                expected_cagr=target.expected_cagr,
                expected_timeframe_months=target.expected_timeframe_months,
                target_source=target.source,
                target_version=target.thesis_version,
                confidence_score=journal.confidence_score if journal else None,
                actual_return_pct=actual_return,
                annualized_return_pct=annualized_return,
                days_held=days_held,
                current_price=position.current_price,
                status=status,
                thesis_still_valid=None  # User needs to assess this
            ))

        # Sort by status (needs_attention first)
        status_order = {'needs_attention': 0, 'behind': 1, 'on_track': 2, 'exceeding': 3, 'no_target': 4}
        results.sort(key=lambda x: status_order.get(x.status, 99))

        return results
    
    def _assess_thesis_status(
        self,
        expected_cagr: Optional[float],
        annualized_return: float,
        total_return: float,
        days_held: int
    ) -> str:
        """
        Assess how the position is tracking vs the expectation set at purchase.

        Args:
            expected_cagr: Annual return % (CAGR) expected
            annualized_return: CAGR of the position
            total_return: Total return % (for short-term positions)
            days_held: Days the position has been held

        Returns:
            Status: 'exceeding', 'on_track', 'behind', 'needs_attention', or
            'no_target' when no expected return was recorded
        """

        if expected_cagr is None:
            # Without a target there is no plan to be ahead of or behind.
            # A loss still needs a look, as it does when a target exists.
            return 'needs_attention' if total_return < 0 else 'no_target'

        comparison = compare_to_expected_cagr(
            expected_cagr, total_return, days_held, annualized_return)
        comparison_return = comparison.actual
        expected_comparison = comparison.expected

        # Compare actual to expected
        if comparison_return >= expected_comparison * 1.2:
            return 'exceeding'  # Beating expectations by 20%+
        elif comparison_return >= expected_comparison * 0.8:
            return 'on_track'  # Within 80-120% of expectations
        elif comparison_return >= 0:
            return 'behind'  # Positive but below expectations
        else:
            return 'needs_attention'  # Losing money


# ============================================================
# Convenience Functions (cached to avoid redundant computation)
# ============================================================

# Not cached: Met / Not Met and the destination-analysis edits change this list,
# and a stale copy keeps resolved checkpoints on the reminders page. It is one
# indexed query.
def get_upcoming_checkpoints(user_id: int, days_ahead: int = 30) -> Dict[str, List[CheckpointReminder]]:
    """Get upcoming and overdue checkpoints"""
    service = PortfolioIntelligenceService(user_id)
    return service.get_upcoming_checkpoints(days_ahead)


@cache.memoize(timeout=300)  # 5 min — position data changes with price refreshes
def get_return_target(user_id: int, company_id: int) -> ReturnTarget:
    """The return target in effect for one company (see _resolve_return_target)."""
    journal = opening_buy_decision(user_id, company_id)
    theses = ThesisEvolution.query.filter_by(
        user_id=user_id,
        company_id=company_id
    ).order_by(ThesisEvolution.version.desc()).all()
    return _resolve_return_target(journal, theses)


def get_thesis_reality_check(user_id: int) -> List[ThesisReality]:
    """Get thesis vs reality comparison for active positions"""
    service = PortfolioIntelligenceService(user_id)
    return service.get_thesis_reality_check()
