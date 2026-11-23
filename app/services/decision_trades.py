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
The trade dataset behind Decision Intelligence's research numbers (#439).

One DecisionTrade per round trip (0 shares to 0 shares), built from the user's
decision outcomes (received holdings are not decisions and are left out).

Returns:
- Closed trade: the stored ``realized_return_pct``.
- Open trade: what that return would be if the shares still held were sold at the
  position's ``current_value`` now. Open trades with no position price are left out.

Limitations:
- Returns leave out dividends, matching the stored realized return, so a trade's
  return here can differ from the position's lifetime return.
- The research class comes from the project and score stored on the outcome at its
  last sync (the project's quality then, not at entry); see ``classify_research``.
- An open trade whose outcome row no longer matches the live round trip (the
  transactions changed and the sync has not run) is skipped until the next sync.

Nothing here fetches prices or writes; it is safe on every page render.
"""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import joinedload

from app.models import DecisionJournal, PortfolioPosition, Transaction
from app.models.ai_intelligence import ResearchOutcome
from app.models.portfolio import _walk_fifo
from app.services.decision_quality import classify_research
from app.services.outcome_tracking import decision_outcomes
from app.services.portfolio_intelligence import outcome_hold_days
from app.services.position_returns import MIN_DAYS_FOR_ANNUALIZED_COMPARISON
from app.utils.financial_utils import calculate_cagr
from app.utils.grading import score_to_grade
from app.utils.time_utils import date, days_between, now_utc


@dataclass
class DecisionTrade:
    outcome: ResearchOutcome            # the trade's row, company eager-loaded
    company_id: int
    entry_date: date
    exit_date: Optional[date]           # None while open
    is_closed: bool
    return_pct: float
    days: int                           # entry to exit, or entry to as_of while open
    annualized_pct: Optional[float]     # CAGR of return_pct; None under MIN_DAYS_FOR_ANNUALIZED_COMPARISON days
    research: str                       # 'none' | 'low' | 'high'
    grade: Optional[str]                # letter grade when the outcome has a score
    opening: Optional[DecisionJournal]  # the trade's opening decision, None if it has none
    confidence: Optional[int]           # opening's confidence, None for no or an imported opening
    expected_cagr: Optional[float]      # opening's expected return, same rule

    @property
    def is_gain(self) -> bool:
        return self.return_pct > 0


def _open_trips(user_id: int, outcomes: List[ResearchOutcome]) -> dict:
    """The open round trip and what is left in the queue, keyed by company id (one query for all)."""
    company_ids = {o.company_id for o in outcomes}
    if not company_ids:
        return {}
    positions = {
        p.company_id: p for p in PortfolioPosition.query.filter(
            PortfolioPosition.user_id == user_id,
            PortfolioPosition.company_id.in_(company_ids),
            PortfolioPosition.is_active.is_(True),
        ).all()
    }
    by_company = defaultdict(list)
    for txn in Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.company_id.in_(positions.keys()),
    ).order_by(Transaction.date.asc(), Transaction.id.asc()).all():
        by_company[txn.company_id].append(txn)

    open_trips = {}
    for company_id, position in positions.items():
        fifo = _walk_fifo(by_company[company_id])
        if fifo.round_trips and not fifo.round_trips[-1].is_closed:
            open_trips[company_id] = (position, fifo.round_trips[-1], fifo.total_cost)
    return open_trips


def _open_return_pct(position, trip, queued_cost) -> Optional[float]:
    """Return if the open shares were sold at the position's value now, or None when it cannot be valued."""
    if position.current_value is None:
        return None
    basis = trip.sold_cost + queued_cost
    if basis <= 0:
        return None
    return float((trip.sell_proceeds + Decimal(str(position.current_value)) - basis) / basis * 100)


def decision_trades(user_id: int, as_of: Optional[date] = None) -> List[DecisionTrade]:
    """The user's decision trades, ordered by (entry date, outcome id)."""
    as_of = as_of or now_utc().date()
    outcomes = decision_outcomes(user_id).options(joinedload(ResearchOutcome.company)).all()

    journal_ids = {o.decision_journal_id for o in outcomes if o.decision_journal_id is not None}
    journals = {
        j.id: j for j in DecisionJournal.query.filter(DecisionJournal.id.in_(journal_ids)).all()
    } if journal_ids else {}
    open_trips = _open_trips(user_id, [o for o in outcomes if o.exit_date is None])

    trades = []
    for outcome in outcomes:
        if outcome.exit_date is not None:
            if outcome.realized_return_pct is None:
                continue
            return_pct = float(outcome.realized_return_pct)
            days = outcome_hold_days(outcome)
            if days is None:
                continue  # no stored hold days and a date missing: cannot be measured
        else:
            found = open_trips.get(outcome.company_id)
            if found is None or found[1].entry_date != outcome.decision_date:
                continue  # no live open trip, or the row is stale until the next sync
            position, trip, queued_cost = found
            return_pct = _open_return_pct(position, trip, queued_cost)
            if return_pct is None:
                continue
            days = days_between(outcome.decision_date, as_of)

        opening = journals.get(outcome.decision_journal_id)
        has_values = opening is not None and not opening.is_imported
        score = outcome.research_quality_score
        trades.append(DecisionTrade(
            outcome=outcome,
            company_id=outcome.company_id,
            entry_date=outcome.decision_date,
            exit_date=outcome.exit_date,
            is_closed=outcome.exit_date is not None,
            return_pct=return_pct,
            days=days,
            annualized_pct=calculate_cagr(return_pct, days) if days >= MIN_DAYS_FOR_ANNUALIZED_COMPARISON else None,
            research=classify_research(outcome),
            grade=score_to_grade(score) if score is not None else None,
            opening=opening,
            confidence=opening.confidence_score if has_values else None,
            expected_cagr=opening.expected_cagr if has_values else None,
        ))
    trades.sort(key=lambda t: (t.entry_date, t.outcome.id))
    return trades
