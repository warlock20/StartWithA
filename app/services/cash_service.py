# Investment Checklist Platform
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
Cash Service
Handles all cash balance tracking logic for the portfolio.
Cash balance is materialized on User for fast reads, recomputed from transactions when needed.
"""

import logging
from datetime import timedelta
from decimal import Decimal

from app import db
from app.models.portfolio import Transaction
from app.models.user import User
from app.utils.time_utils import now_utc

logger = logging.getLogger(__name__)


class CashService:
    """Service for managing portfolio cash balance."""

    @staticmethod
    def get_cash_impact(txn):
        """
        Calculate the cash impact of a single transaction in base currency.

        Returns:
            Decimal: Positive for cash inflows, negative for outflows.
        """
        if txn.type == 'DEPOSIT':
            return Decimal(str(txn.cash_amount_base or txn.cash_amount or 0))

        elif txn.type == 'WITHDRAWAL':
            return -Decimal(str(txn.cash_amount_base or txn.cash_amount or 0))

        elif txn.type == 'BUY':
            price = Decimal(str(txn.price_per_share_base or txn.price_per_share))
            fees = Decimal(str(txn.fees_base or txn.fees or 0))
            return -(Decimal(str(txn.quantity)) * price + fees)

        elif txn.type == 'SELL':
            price = Decimal(str(txn.price_per_share_base or txn.price_per_share))
            fees = Decimal(str(txn.fees_base or txn.fees or 0))
            return Decimal(str(txn.quantity)) * price - fees

        elif txn.type == 'DIVIDEND':
            price = Decimal(str(txn.price_per_share_base or txn.price_per_share))
            return Decimal(str(txn.quantity)) * price

        # SPLIT, SPINOFF — no cash impact
        return Decimal('0.00')

    @staticmethod
    def recalculate_cash_balance(user_id):
        """
        Full recompute of cash balance from all transactions.
        Used for migration, force-resync, edit/delete operations.

        Returns:
            Decimal: The recalculated cash balance.
        """
        transactions = Transaction.query.filter_by(
            user_id=user_id
        ).order_by(Transaction.date.asc(), Transaction.id.asc()).all()

        balance = Decimal('0.00')
        for txn in transactions:
            balance += CashService.get_cash_impact(txn)

        user = User.query.get(user_id)
        if user:
            user.cash_balance = balance
            db.session.commit()

        logger.info(f"Recalculated cash balance for user {user_id}: {balance}")
        return balance

    @staticmethod
    def update_after_transaction(user_id, transaction):
        """
        Incremental update: add a single transaction's cash impact to user.cash_balance.
        If a BUY pushes cash negative, auto-creates a DEPOSIT for the shortfall.

        Returns:
            str or None: Notification message if an auto-deposit was created.
        """
        impact = CashService.get_cash_impact(transaction)
        if impact == Decimal('0.00'):
            return None

        user = User.query.get(user_id)
        if not user:
            return None

        current = Decimal(str(user.cash_balance or 0))
        new_balance = current + impact
        user.cash_balance = new_balance
        db.session.commit()

        logger.info(f"Cash balance updated for user {user_id}: impact={impact}, balance={new_balance}")

        # Auto-create deposit if cash went negative from a BUY
        if new_balance < 0 and transaction.type == 'BUY':
            shortfall = abs(new_balance)
            deposit = Transaction(
                user_id=user_id,
                type='DEPOSIT',
                date=transaction.date,
                cash_amount=shortfall,
                cash_amount_base=shortfall,
                currency=user.base_currency,
                notes=f'Auto-created: capital inflow to cover purchase'
            )
            db.session.add(deposit)
            user.cash_balance = Decimal('0.00')
            db.session.commit()

            logger.info(f"Auto-created deposit of {shortfall} for user {user_id} (cash was negative after BUY)")
            return f"A capital inflow of {shortfall:,.2f} was automatically recorded to cover this purchase."

        return None

    @staticmethod
    def infer_initial_deposit(user_id):
        """
        Infer the minimum initial capital needed to fund all trades.

        Simulates cash flow chronologically (without any deposits) and finds the
        peak negative balance. That peak represents the minimum single deposit
        the user must have made to cover all their purchases.

        This correctly handles reinvested sell proceeds — if you buy $30K, sell
        for $35K, then buy $35K, the peak deficit is $30K (not $65K).

        Returns:
            Decimal: Inferred initial deposit amount.
        """
        transactions = Transaction.query.filter_by(
            user_id=user_id
        ).filter(
            Transaction.type.in_(['BUY', 'SELL', 'DIVIDEND'])
        ).order_by(Transaction.date.asc(), Transaction.id.asc()).all()

        balance = Decimal('0.00')
        min_balance = Decimal('0.00')

        for txn in transactions:
            balance += CashService.get_cash_impact(txn)
            if balance < min_balance:
                min_balance = balance

        # The absolute value of the most negative point is the minimum deposit needed
        return abs(min_balance)

    @staticmethod
    def create_initial_deposit(user_id, amount, base_currency):
        """
        Create the auto-inferred initial DEPOSIT transaction.
        Dated one day before the user's first BUY transaction.

        Args:
            user_id: User ID
            amount: Deposit amount in base currency
            base_currency: User's base currency code
        """
        first_buy = Transaction.query.filter_by(
            user_id=user_id, type='BUY'
        ).order_by(Transaction.date.asc()).first()

        deposit_date = first_buy.date - timedelta(days=1) if first_buy else now_utc().date()

        deposit = Transaction(
            user_id=user_id,
            type='DEPOSIT',
            date=deposit_date,
            cash_amount=Decimal(str(amount)),
            cash_amount_base=Decimal(str(amount)),
            currency=base_currency,
            notes='Auto-calculated initial capital'
        )
        db.session.add(deposit)
        db.session.commit()

        # Recalculate from scratch to ensure consistency
        CashService.recalculate_cash_balance(user_id)

        logger.info(f"Created initial deposit of {amount} {base_currency} for user {user_id}")
