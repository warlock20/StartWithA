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
A position's return, counting everything it earned: one definition for every page.

``unrealized_gain_loss_pct`` only covers the shares still held, so it leaves out
dividends and the gains on shares already sold, and annualizing it over
``days_held`` (from the first purchase ever) mixes a short-lived cost base with a
long holding period. This module measures the position from its own cash flows
instead (see ``_FifoResult.cash_flows``):

    total_gain        = unrealized + realized (trading and dividends)
    capital_invested  = cost of every lot bought or received
    total_return_pct  = total_gain / capital_invested
    annualized_pct    = XIRR of the flows, with the market value of the shares
                        held as the closing flow (money-weighted, so a top-up made
                        last month is not treated as if it had been held for years)

For a single purchase held with no sales or dividends, the annualized figure is
the plain CAGR. A closed position is measured up to its last flow.

Prices are read from the materialized position (``current_value``); nothing here
fetches prices, so it is safe on every page render.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, Iterable, Optional

from app.models.portfolio import Transaction, _walk_fifo
from app.utils.financial_utils import calculate_cagr, calculate_xirr
from app.utils.time_utils import now_utc

ZERO = Decimal('0.00')
# Below this many days a return is not annualized: a few days' move blown up to a
# yearly rate is meaningless. compare_to_expected_cagr uses the same threshold.
MIN_DAYS_FOR_ANNUALIZED_COMPARISON = 30


@dataclass
class PositionReturn:
    """Lifetime result of one position, in the user's base currency."""
    total_gain: Decimal                 # unrealized + realized, dividends included
    capital_invested: Decimal           # every lot bought or received
    total_return_pct: Optional[float]   # total_gain / capital_invested
    annualized_pct: Optional[float]     # XIRR; None under MIN_DAYS_FOR_ANNUALIZED_COMPARISON days
    days: int                           # first flow to today (open) or to the last flow (closed)

    @property
    def is_gain(self) -> bool:
        return self.total_gain > 0


def _measure(position, cash_flows, as_of: date) -> Optional[PositionReturn]:
    """PositionReturn from a position's flows, or None when it cannot be valued yet."""
    if not cash_flows:
        return None

    flows = list(cash_flows)
    if position.is_active:
        if position.current_value is None:
            return None  # no price yet: the open shares cannot be valued
        flows.append((as_of, Decimal(str(position.current_value))))

    capital_invested = -sum((a for _, a in flows if a < 0), ZERO)
    if capital_invested <= 0:
        return None

    total_gain = sum((a for _, a in flows), ZERO)
    total_return_pct = float(total_gain / capital_invested * 100)
    start = min(d for d, _ in flows)
    end = as_of if position.is_active else max(d for d, _ in flows)
    days = (end - start).days

    annualized_pct = None
    if days >= MIN_DAYS_FOR_ANNUALIZED_COMPARISON:
        annualized_pct = calculate_xirr(flows)
        if annualized_pct is None:
            # No sign change or no root (e.g. a total loss): fall back to the plain CAGR
            annualized_pct = calculate_cagr(total_return_pct, days)

    return PositionReturn(
        total_gain=total_gain,
        capital_invested=capital_invested,
        total_return_pct=total_return_pct,
        annualized_pct=annualized_pct,
        days=days,
    )


def position_returns(positions: Iterable, as_of: Optional[date] = None) -> Dict[int, PositionReturn]:
    """
    PositionReturn for each position, keyed by company_id.

    Loads the transactions of all the positions in one query. Positions that
    cannot be valued (no transactions, or open with no price yet) are left out,
    so callers treat a missing key as "no return".
    """
    positions = list(positions)
    if not positions:
        return {}
    as_of = as_of or now_utc().date()

    user_ids = {p.user_id for p in positions}
    company_ids = {p.company_id for p in positions}
    by_key = defaultdict(list)
    for txn in Transaction.query.filter(
        Transaction.user_id.in_(user_ids),
        Transaction.company_id.in_(company_ids),
    ).order_by(Transaction.date.asc(), Transaction.id.asc()).all():
        by_key[(txn.user_id, txn.company_id)].append(txn)

    results = {}
    for position in positions:
        fifo = _walk_fifo(by_key.get((position.user_id, position.company_id), []))
        measured = _measure(position, fifo.cash_flows, as_of)
        if measured is not None:
            results[position.company_id] = measured
    return results


def position_return(position, as_of: Optional[date] = None) -> Optional[PositionReturn]:
    """PositionReturn for one position, or None when it cannot be valued."""
    return position_returns([position], as_of).get(position.company_id)


def holding_return_fields(measured: Optional[PositionReturn]) -> dict:
    """The return fields of a holdings row (dashboard table and the refresh APIs).

    ``gain_loss`` is the lifetime gain (unrealized + realized + dividends), so
    the Total P/L and Total Return columns agree with the position page.
    """
    if measured is None:
        return {'gain_loss': None, 'gain_loss_pct': None, 'annualized_pct': None}
    return {
        'gain_loss': float(round(measured.total_gain)),
        'gain_loss_pct': round(measured.total_return_pct, 1),
        'annualized_pct': round(measured.annualized_pct, 1) if measured.annualized_pct is not None else None,
    }
