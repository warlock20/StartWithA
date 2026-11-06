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
Imported capital timing (issue #347).

Importing a portfolio gives us trades but not the deposits that funded them.
The capital is inferred, and the XIRR depends on *when* it is assumed to have
come in. Two readings are offered: gradually, on the dates of the purchases
that needed it (the default), or all at once before the first purchase.

Only deposits this module wrote (identified by their notes) are ever replaced.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple

from app import db
from app.models.portfolio import Transaction
from app.services.cash_service import CashService
from app.utils.time_utils import now_utc

logger = logging.getLogger(__name__)

LUMP_SUM = 'lump_sum'
GRADUAL = 'gradual'
INITIAL_CAPITAL_NOTE = 'Auto-calculated initial capital'
GRADUAL_CAPITAL_NOTE = 'Auto-calculated capital, as purchased'
AUTO_NOTES = (INITIAL_CAPITAL_NOTE, GRADUAL_CAPITAL_NOTE)


def _auto_deposits(user_id: int) -> List[Transaction]:
    return Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.type == 'DEPOSIT',
        Transaction.notes.in_(AUTO_NOTES),
    ).all()


def _deposit_amount(txn: Transaction) -> Decimal:
    return Decimal(str(txn.cash_amount_base if txn.cash_amount_base is not None else txn.cash_amount or 0))


def gradual_funding_flows(user_id: int, total: Decimal) -> List[Tuple[date, Decimal]]:
    """
    Spread ``total`` over the dates of the transactions that ran cash negative.

    Walks the user's own transactions (auto-calculated capital excluded) and,
    whenever the running cash balance dips below zero, draws the shortfall from
    ``total`` on that date. Whatever is left over goes on the first BUY date.
    """
    total = Decimal(str(total))
    # Same day: cash that comes in (sells, dividends, deposits) is applied
    # before the purchases, so it funds them rather than imported capital.
    transactions = sorted(
        Transaction.query.filter_by(user_id=user_id).all(),
        key=lambda t: (t.date, t.type == 'BUY', t.id),
    )

    balance = Decimal('0')
    budget = total
    draws = {}
    for txn in transactions:
        if txn.type == 'DEPOSIT' and txn.notes in AUTO_NOTES:
            continue
        balance += CashService.get_cash_impact(txn)
        if balance < 0 and budget > 0:
            draw = min(-balance, budget)
            draws[txn.date] = draws.get(txn.date, Decimal('0')) + draw
            budget -= draw
            balance += draw

    if budget > 0:
        first_buy = next((t.date for t in transactions if t.type == 'BUY'), None)
        anchor = first_buy or (transactions[0].date if transactions else now_utc().date())
        draws[anchor] = draws.get(anchor, Decimal('0')) + budget

    return sorted(draws.items())


def record_imported_capital(user_id: int, amount: Decimal, mode: str, base_currency: str) -> None:
    """Replace the user's auto-calculated capital deposits with ``amount`` in ``mode``."""
    if mode not in (LUMP_SUM, GRADUAL):
        raise ValueError(f'Unknown capital timing: {mode!r}')

    amount = Decimal(str(amount))
    for row in _auto_deposits(user_id):
        db.session.delete(row)
    db.session.flush()

    if mode == LUMP_SUM:
        first_buy = Transaction.query.filter_by(user_id=user_id, type='BUY').order_by(
            Transaction.date.asc()
        ).first()
        deposit_date = first_buy.date - timedelta(days=1) if first_buy else now_utc().date()
        flows = [(deposit_date, amount)]
        note = INITIAL_CAPITAL_NOTE
    else:
        flows = gradual_funding_flows(user_id, amount)
        note = GRADUAL_CAPITAL_NOTE

    for flow_date, flow_amount in flows:
        db.session.add(Transaction(
            user_id=user_id, type='DEPOSIT', date=flow_date,
            cash_amount=flow_amount, cash_amount_base=flow_amount,
            currency=base_currency, notes=note,
        ))
    db.session.commit()

    CashService.recalculate_cash_balance(user_id)
    logger.info(f"Recorded imported capital {amount} {base_currency} ({mode}) for user {user_id}")


def imported_capital_mode(user_id: int) -> Optional[str]:
    notes = {row.notes for row in _auto_deposits(user_id)}
    if GRADUAL_CAPITAL_NOTE in notes:
        return GRADUAL
    if INITIAL_CAPITAL_NOTE in notes:
        return LUMP_SUM
    return None


def imported_capital_total(user_id: int) -> Decimal:
    return sum((_deposit_amount(row) for row in _auto_deposits(user_id)), Decimal('0'))


def switch_imported_capital(user_id: int, mode: str) -> bool:
    """Re-date the auto-calculated capital, keeping its total. False if there is none."""
    rows = _auto_deposits(user_id)
    if not rows:
        return False
    record_imported_capital(user_id, imported_capital_total(user_id), mode, rows[0].currency)
    return True
