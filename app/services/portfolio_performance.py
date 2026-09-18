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
Portfolio Performance Service

Single source of truth for portfolio-level value and return (issue #336).

The portfolio is measured against the capital the user actually put in:

    capital_invested = deposits - withdrawals
    total_value      = market value of open positions + cash balance
    total_return     = total_value - capital_invested
                     = unrealized + realized (trading) + dividends

Every component is counted exactly once, so the dashboard tiles reconcile.
The previous per-page calculations each used a different base — open-position
FIFO cost, price-only appreciation, or unrealized + dividends on active
positions only — which is why Total Value - Cost Basis never matched Total P/L.
"""

import logging
from decimal import Decimal

from sqlalchemy import func

from app import db
from app.models.portfolio import PortfolioPosition, Transaction
from app.models.user import User
from app.services.cash_service import CashService

logger = logging.getLogger(__name__)

ZERO = Decimal('0.00')

# Transaction types that move capital in or out of the portfolio.
CASH_FLOW_TYPES = ('DEPOSIT', 'WITHDRAWAL')


def _dec(value):
    """Coerce a possibly-None numeric to Decimal."""
    return Decimal(str(value)) if value is not None else ZERO


class PortfolioPerformanceService:
    """Computes portfolio value and return for a user."""

    @staticmethod
    def get_capital_invested(user_id):
        """
        Net capital the user has put into the portfolio.

        Deposits minus withdrawals. When no cash transactions exist yet — an
        imported portfolio before the user confirms the cash-setup banner — fall
        back to the minimum deposit that would have funded the trades, which is
        the same figure the banner offers.

        Returns:
            Decimal: Net capital invested, in base currency.
        """
        return PortfolioPerformanceService._capital_invested(user_id)[0]

    @staticmethod
    def _capital_invested(user_id):
        """
        Capital invested, plus the part of it that had to be inferred.

        Returns:
            tuple[Decimal, Decimal]: (capital_invested, inferred_amount). The
            second element is non-zero only before cash setup, where it is the
            deposit the user has not recorded yet — money the cash balance is
            still short of.
        """
        rows = db.session.query(
            Transaction.type,
            func.sum(func.coalesce(
                Transaction.cash_amount_base, Transaction.cash_amount, 0
            )),
        ).filter(
            Transaction.user_id == user_id,
            Transaction.type.in_(CASH_FLOW_TYPES),
        ).group_by(Transaction.type).all()

        if not rows:
            inferred = CashService.infer_initial_deposit(user_id)
            return inferred, inferred

        net = ZERO
        for txn_type, total in rows:
            amount = _dec(total)
            net += amount if txn_type == 'DEPOSIT' else -amount
        return net, ZERO

    @staticmethod
    def get_performance(user_id):
        """
        Portfolio value and return for a user.

        Reads the materialized position and cash rows — no price fetching, so
        this is safe to call on every page render.

        Returns:
            dict: {
                'capital_invested': Decimal,   # deposits - withdrawals
                'positions_value': Decimal,    # market value, open positions
                'cash_balance': Decimal,
                'total_value': Decimal,        # positions_value + cash_balance
                'total_return': Decimal,       # total_value - capital_invested
                'total_return_pct': Decimal,
                'unrealized_gain_loss': Decimal,   # open positions
                'realized_gain_loss': Decimal,     # trading only, lifetime
                'total_dividends': Decimal,        # lifetime
                'securities_cost': Decimal,        # FIFO cost of open positions
                'positions_count': int,
            }
        """
        positions = PortfolioPosition.query.filter_by(user_id=user_id).all()

        positions_value = ZERO
        securities_cost = ZERO
        unrealized = ZERO
        dividends = ZERO
        realized_incl_dividends = ZERO
        open_count = 0

        for position in positions:
            # Closed positions keep their last known current_value, so market
            # value and cost come from open positions only.
            if position.is_active:
                open_count += 1
                positions_value += _dec(position.current_value)
                securities_cost += _dec(position.total_cost)
                unrealized += _dec(position.unrealized_gain_loss)

            # Realized results and dividends are lifetime figures: a fully
            # exited winner still counts toward the portfolio's return.
            dividends += _dec(position.total_dividends)
            realized_incl_dividends += _dec(position.realized_gain_loss)

        # PortfolioPosition.realized_gain_loss bundles dividends in (see
        # calculate_fifo_cost_basis). Split them so each component is counted once.
        realized = realized_incl_dividends - dividends

        user = User.query.get(user_id)
        cash_balance = _dec(user.cash_balance) if user else ZERO

        capital_invested, inferred = PortfolioPerformanceService._capital_invested(user_id)

        # Before cash setup there is no DEPOSIT row, so the materialized balance
        # is short by the capital that funded the trades. Credit the inferred
        # deposit to cash as well, otherwise it is subtracted from value while
        # being added to capital and the return is wrong by twice it.
        cash_balance += inferred

        total_value = positions_value + cash_balance
        total_return = total_value - capital_invested
        total_return_pct = (
            (total_return / capital_invested * 100) if capital_invested > 0 else ZERO
        )

        return {
            'capital_invested': capital_invested,
            'positions_value': positions_value,
            'cash_balance': cash_balance,
            'total_value': total_value,
            'total_return': total_return,
            'total_return_pct': total_return_pct,
            'unrealized_gain_loss': unrealized,
            'realized_gain_loss': realized,
            'total_dividends': dividends,
            'securities_cost': securities_cost,
            'positions_count': open_count,
        }
