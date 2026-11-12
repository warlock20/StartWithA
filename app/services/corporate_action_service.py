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
Corporate actions: mergers, spin-offs, stock dividends and splits.

An action is one CorporateAction row plus the Transaction rows ("legs") it
writes. Everything downstream (FIFO, cash, outcomes) reads the legs, so every
write here ends by recalculating the companies it touched.
"""

import logging
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional, Set

from app import db
from app.models.company import Company
from app.models.portfolio import (
    CORPORATE_ACTION_TYPES, CorporateAction, Transaction, _load_transactions, _walk_fifo,
    fifo_state_on, first_oversell, shares_held_on, update_portfolio_position_for_company,
)
from app.models.user import User
from app.services.cash_service import CashService
from app.services.company_lookup import get_or_create_company_by_ticker
from app.services.currency_service import CurrencyService
from app.services.outcome_tracking import safe_sync_outcomes
from app.utils.time_utils import date, now_utc

logger = logging.getLogger(__name__)

CENT = Decimal('0.01')
ZERO = Decimal('0')


class CorporateActionError(ValueError):
    """Invalid corporate action. str(e) is the message shown to the user."""


@dataclass
class CorporateActionInput:
    action_type: str                      # CORPORATE_ACTION_TYPES
    effective_date: date
    source_company_id: int
    target_company_id: Optional[int] = None
    target_ticker: Optional[str] = None   # used when target_company_id is None (merger/spin-off)
    shares_received: Optional[int] = None
    price_per_share: Optional[Decimal] = None   # merger: B close; stock dividend: booked value
    cash_received: Decimal = Decimal('0')
    fees: Decimal = Decimal('0')
    ratio: Optional[Decimal] = None       # merger: informational; split: required
    cost_allocation_pct: Optional[Decimal] = None   # spin-off: required, 0 < pct < 100
    zero_cost: bool = False               # stock dividend only
    notes: str = ''


@dataclass
class PositionChange:
    company_id: int
    ticker: str
    shares_before: int
    shares_after: int
    cost_before: Decimal
    cost_after: Decimal


@dataclass
class ActionPreview:
    changes: List[PositionChange]
    realized_gain_base: Decimal     # change in realized_gain_loss across affected companies
    dividend_income_base: Decimal   # change in total_dividends
    cash_change_base: Decimal       # sum of get_cash_impact over the legs


def _cents(value) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def _currency(company: Company) -> str:
    return company.reporting_currency or CurrencyService.detect_currency_from_ticker(company.ticker_symbol)


def _label(txn: Transaction) -> str:
    return f"{txn.type} on {txn.date.isoformat()}"


def _validate_input(data: CorporateActionInput) -> None:
    """Checks that need no database."""
    if data.action_type not in CORPORATE_ACTION_TYPES:
        raise CorporateActionError(f'Unknown corporate action type: {data.action_type}')
    if data.effective_date > now_utc().date():
        raise CorporateActionError('The effective date cannot be in the future.')
    if (data.cash_received or ZERO) < 0:
        raise CorporateActionError('Cash received cannot be negative.')
    if (data.fees or ZERO) < 0:
        raise CorporateActionError('Fees cannot be negative.')

    kind = data.action_type
    has_target = bool(data.target_company_id or (data.target_ticker or '').strip())
    shares = data.shares_received or 0

    if kind == 'MERGER':
        if has_target:
            if shares < 1:
                raise CorporateActionError('Shares received must be at least 1.')
            if data.price_per_share is None or data.price_per_share <= 0:
                raise CorporateActionError("Enter the new company's closing price on the effective date.")
        elif (data.cash_received or ZERO) <= 0:
            raise CorporateActionError('A cash-only takeover needs the cash received.')
    elif kind == 'SPINOFF':
        if not has_target:
            raise CorporateActionError('Choose the company that was spun off.')
        if shares < 1:
            raise CorporateActionError('Shares received must be at least 1.')
        pct = data.cost_allocation_pct
        if pct is None or not (ZERO < pct < 100):
            raise CorporateActionError('Cost allocation must be above 0% and below 100%.')
    elif kind == 'STOCK_DIVIDEND':
        if shares < 1:
            raise CorporateActionError('Shares received must be at least 1.')
        if not data.zero_cost and (data.price_per_share is None or data.price_per_share <= 0):
            raise CorporateActionError('Enter the booked value per share, or choose zero cost.')
    elif kind == 'SPLIT':
        if data.ratio is None or data.ratio <= 0:
            raise CorporateActionError('The split ratio must be greater than zero.')


def _resolve_target(user: User, data: CorporateActionInput, source: Company) -> Optional[Company]:
    """B for a merger or spin-off (created from its ticker if new); A itself otherwise."""
    if data.action_type in ('STOCK_DIVIDEND', 'SPLIT'):
        return source
    if data.target_company_id:
        target = Company.query.filter_by(id=data.target_company_id, user_id=user.id).first()
        if not target:
            raise CorporateActionError('The selected company was not found.')
    elif (data.target_ticker or '').strip():
        target = get_or_create_company_by_ticker(user.id, data.target_ticker)
    else:
        return None
    if target.id == source.id:
        raise CorporateActionError('The new company must differ from the one you held.')
    return target


def _leg(user: User, action: CorporateAction, company: Company, kind: str, qty: int,
         rate: Decimal, price: Decimal, value: Decimal, cash: Decimal = ZERO,
         fees: Decimal = ZERO) -> Transaction:
    """One leg. price, cash and fees are in the company's currency; value is already base."""
    price_base = _cents(price * rate)
    return Transaction(
        user_id=user.id, company_id=company.id, type=kind, date=action.effective_date,
        quantity=qty, currency=_currency(company),
        price_per_share=_cents(price), price_per_share_base=price_base,
        cash_amount=_cents(cash), cash_amount_base=_cents(cash * rate),
        fees=_cents(fees), fees_base=_cents(fees * rate),
        exchange_rate=rate, exchange_rate_date=action.effective_date,
        corporate_value_base=value, corporate_action_id=action.id, notes=action.notes,
    )


def _resolve_rates(user: User, data: CorporateActionInput) -> Dict[str, Decimal]:
    """
    Rate to base for every currency the action's legs need, keyed by currency.

    Runs before the write's savepoint: CurrencyService caches a fetched rate with
    db.session.commit(), which would end the savepoint (and the transaction) if it
    ran inside it. A typed ticker that is not a company yet uses the currency the
    company will be created with.
    """
    _validate_input(data)  # no rate is fetched (and cached) for a future or malformed action
    if data.action_type == 'SPLIT':
        return {}
    currencies = set()
    source = Company.query.filter_by(id=data.source_company_id, user_id=user.id).first()
    if source is not None:
        currencies.add(_currency(source))
    if data.action_type in ('MERGER', 'SPINOFF'):
        ticker = (data.target_ticker or '').strip().upper()
        target = None
        if data.target_company_id:
            target = Company.query.filter_by(id=data.target_company_id, user_id=user.id).first()
        elif ticker:
            target = Company.query.filter(
                Company.user_id == user.id, db.func.upper(Company.ticker_symbol) == ticker).first()
            if target is None:
                currencies.add(CurrencyService.detect_currency_from_ticker(ticker))
        if target is not None:
            currencies.add(_currency(target))
    return {cur: Decimal(str(CurrencyService.get_exchange_rate(cur, user.base_currency, data.effective_date)))
            for cur in currencies}


def _rate(rates: Dict[str, Decimal], company: Company) -> Decimal:
    return rates[_currency(company)]


def _build_legs(user: User, data: CorporateActionInput, action: CorporateAction,
                source: Company, target: Optional[Company], rates: Dict[str, Decimal]) -> List[Transaction]:
    on = data.effective_date
    cash = data.cash_received or ZERO
    fees = data.fees or ZERO
    a_shares = shares_held_on(source.id, user.id, on)
    if data.action_type == 'SPLIT':
        # The exact ratio lives on the action (the walk reads it there). The leg is
        # display only: quantity 0 like the importer's, no exchange rate, no money.
        return [Transaction(
            user_id=user.id, company_id=source.id, type='SPLIT', date=on, quantity=0,
            currency=_currency(source), price_per_share=_cents(data.ratio),
            price_per_share_base=_cents(data.ratio), fees=ZERO, fees_base=ZERO,
            corporate_action_id=action.id, notes=action.notes)]
    rate_a = _rate(rates, source)

    if data.action_type == 'MERGER':
        value = ZERO
        legs = []
        if target is not None:
            rate_b = _rate(rates, target)
            value = _cents(data.shares_received * data.price_per_share * rate_b)
        cash_base = _cents(cash * rate_a)
        out_price_base = (value + cash_base) / a_shares
        out = _leg(user, action, source, 'MERGER_OUT', a_shares, rate_a,
                   out_price_base / rate_a, value, cash, fees)
        legs.append(out)
        if target is not None:
            legs.append(_leg(user, action, target, 'MERGER_IN', data.shares_received, rate_b,
                             data.price_per_share, value))
        return legs

    if data.action_type == 'SPINOFF':
        cost = fifo_state_on(source.id, user.id, on).total_cost
        if cost <= 0:
            raise CorporateActionError(
                f'{source.ticker_symbol} has no cost basis on {on.isoformat()} to allocate to the spin-off.')
        value = _cents(cost * data.cost_allocation_pct / 100)
        rate_b = _rate(rates, target)
        return [
            _leg(user, action, source, 'SPINOFF_PARENT', a_shares, rate_a, ZERO, value),
            _leg(user, action, target, 'SPINOFF_CHILD', data.shares_received, rate_b,
                 value / rate_b / data.shares_received, value, cash, fees),
        ]

    if data.action_type == 'STOCK_DIVIDEND':
        price = ZERO if data.zero_cost else data.price_per_share
        value = _cents(data.shares_received * price * rate_a)
        return [_leg(user, action, source, 'STOCK_DIVIDEND', data.shares_received, rate_a,
                     price, value, cash, fees)]

    raise CorporateActionError(f'Unknown corporate action type: {data.action_type}')


def _check_source(user: User, data: CorporateActionInput, source: Company, action_id: Optional[int]) -> None:
    if shares_held_on(source.id, user.id, data.effective_date) <= 0:
        raise CorporateActionError(
            f'You held no shares of {source.ticker_symbol} on {data.effective_date.isoformat()}.')
    merged = Transaction.query.filter(
        Transaction.user_id == user.id, Transaction.company_id == source.id,
        Transaction.type == 'MERGER_OUT', Transaction.date > data.effective_date,
    ).order_by(Transaction.date.asc(), Transaction.id.asc()).all()
    merged = [t for t in merged if action_id is None or t.corporate_action_id != action_id]
    if merged:
        raise CorporateActionError(
            f'{source.ticker_symbol} merged on {merged[0].date.isoformat()}; delete that merger first.')
    if data.action_type == 'MERGER':
        later = Transaction.query.filter(
            Transaction.user_id == user.id, Transaction.company_id == source.id,
            Transaction.date > data.effective_date,
        ).order_by(Transaction.date.asc(), Transaction.id.asc()).all()
        later = [t for t in later if action_id is None or t.corporate_action_id != action_id]
        if later:
            names = ', '.join(_label(t) for t in later[:5])
            raise CorporateActionError(
                f'{source.ticker_symbol} has transactions after the merger date ({names}). '
                f'Delete or move them first: those shares no longer exist.')


def _oversold_ids(user: User, company_ids: Set[int]) -> Dict[int, Optional[int]]:
    """Id of each company's first oversold transaction (None when it has none)."""
    result = {}
    for company_id in company_ids:
        bad = first_oversell(company_id, user.id)
        result[company_id] = bad.id if bad is not None else None
    return result


def _check_no_oversell(user: User, company_ids: Set[int], before: Dict[int, Optional[int]]) -> None:
    """Refuse oversells the write introduced; ones already in the history (orphan imports) stay."""
    for company_id in company_ids:
        bad = first_oversell(company_id, user.id)
        if bad is not None and before.get(company_id) != bad.id:
            company = db.session.get(Company, company_id)
            raise CorporateActionError(
                f'{company.ticker_symbol} would be oversold: the {_label(bad)} '
                f'({bad.quantity} shares) has no shares left to sell.')


def _snapshot(user: User, company_ids: Set[int]) -> Dict[int, object]:
    return {cid: _walk_fifo(_load_transactions(cid, user.id)) for cid in company_ids}


def _apply(user: User, data: CorporateActionInput, action_id: Optional[int], rates: Dict[str, Decimal]):
    """
    Write the action and its legs (replacing the legs when action_id is given), then
    check nothing is oversold. Leaves the flushed result in the session; the caller
    owns the savepoint and the commit. rates comes from _resolve_rates, called before
    the savepoint.

    Returns (action, affected company ids).
    """
    _validate_input(data)
    source = Company.query.filter_by(id=data.source_company_id, user_id=user.id).first()
    if not source:
        raise CorporateActionError('The company you held was not found.')

    affected: Set[int] = {source.id}
    action = None
    if action_id is not None:
        action = CorporateAction.query.filter_by(id=action_id, user_id=user.id).first()
        if not action:
            raise CorporateActionError('Corporate action not found.')
        affected.update(cid for cid in (action.source_company_id, action.target_company_id) if cid)
    oversold_before = _oversold_ids(user, affected)
    if action is not None:
        for leg in list(action.legs):
            db.session.delete(leg)
        db.session.flush()
        db.session.expire(action, ['legs'])

    _check_source(user, data, source, action_id)
    target = _resolve_target(user, data, source)
    if target is not None:
        affected.add(target.id)
        if target.id not in oversold_before:
            oversold_before.update(_oversold_ids(user, {target.id}))

    if action is None:
        action = CorporateAction(user_id=user.id)
        db.session.add(action)
    action.action_type = data.action_type
    action.effective_date = data.effective_date
    action.source_company_id = source.id
    action.target_company_id = target.id if target is not None else None
    action.ratio = data.ratio
    action.cost_allocation_pct = data.cost_allocation_pct if data.action_type == 'SPINOFF' else None
    action.notes = (data.notes or '').strip() or None
    db.session.flush()

    for leg in _build_legs(user, data, action, source, target, rates):
        db.session.add(leg)
    db.session.flush()
    db.session.expire(action, ['legs'])

    _check_no_oversell(user, affected, oversold_before)
    return action, affected


def _recalculate(user: User, company_ids: Set[int]) -> None:
    for company_id in company_ids:
        update_portfolio_position_for_company(company_id, user.id)
    for company_id in company_ids:
        safe_sync_outcomes(user.id, company_id)


class CorporateActionService:
    @staticmethod
    def create(user: User, data: CorporateActionInput) -> CorporateAction:
        rates = _resolve_rates(user, data)
        with db.session.begin_nested():
            action, affected = _apply(user, data, None, rates)
            _recalculate(user, affected)
        db.session.commit()
        CashService.recalculate_cash_balance(user.id)
        return action

    @staticmethod
    def update(user: User, action_id: int, data: CorporateActionInput) -> CorporateAction:
        rates = _resolve_rates(user, data)
        with db.session.begin_nested():
            action, affected = _apply(user, data, action_id, rates)
            _recalculate(user, affected)
        db.session.commit()
        CashService.recalculate_cash_balance(user.id)
        return action

    @staticmethod
    def delete(user: User, action_id: int) -> None:
        with db.session.begin_nested():
            action = CorporateAction.query.filter_by(id=action_id, user_id=user.id).first()
            if not action:
                raise CorporateActionError('Corporate action not found.')
            affected = {cid for cid in (action.source_company_id, action.target_company_id) if cid}
            oversold_before = _oversold_ids(user, affected)
            db.session.delete(action)
            db.session.flush()
            _check_no_oversell(user, affected, oversold_before)
            _recalculate(user, affected)
        db.session.commit()
        CashService.recalculate_cash_balance(user.id)

    @staticmethod
    def preview(user: User, data: CorporateActionInput, action_id: Optional[int] = None) -> ActionPreview:
        """What the action would do. Runs the real build in a savepoint and rolls it back."""
        before_ids = {data.source_company_id}
        if data.target_company_id:
            before_ids.add(data.target_company_id)
        if action_id is not None:
            existing = CorporateAction.query.filter_by(id=action_id, user_id=user.id).first()
            if existing:
                before_ids.update(cid for cid in (existing.source_company_id, existing.target_company_id) if cid)
        before = _snapshot(user, before_ids)
        old_cash = ZERO
        if action_id is not None and existing:
            old_cash = sum((CashService.get_cash_impact(leg) for leg in existing.legs), ZERO)

        rates = _resolve_rates(user, data)
        savepoint = db.session.begin_nested()
        try:
            action, affected = _apply(user, data, action_id, rates)
            after = _snapshot(user, affected)
            legs = list(action.legs)
            cash_change = sum((CashService.get_cash_impact(leg) for leg in legs), ZERO)
            tickers = {cid: db.session.get(Company, cid).ticker_symbol for cid in affected}
        finally:
            savepoint.rollback()

        # A company matched by ticker was not known up front; its state is unchanged by the rollback
        before.update(_snapshot(user, affected - set(before)))

        empty = _walk_fifo([])
        changes, realized, dividends = [], ZERO, ZERO
        for cid in sorted(affected | set(before)):
            old, new = before.get(cid, empty), after.get(cid, empty)
            if cid not in tickers:
                tickers[cid] = db.session.get(Company, cid).ticker_symbol
            changes.append(PositionChange(
                company_id=cid, ticker=tickers[cid],
                shares_before=old.total_shares, shares_after=new.total_shares,
                cost_before=old.total_cost, cost_after=new.total_cost))
            realized += new.realized_gain_loss - old.realized_gain_loss
            dividends += new.total_dividends - old.total_dividends
        return ActionPreview(changes=changes, realized_gain_base=realized,
                             dividend_income_base=dividends, cash_change_base=cash_change - old_cash)
