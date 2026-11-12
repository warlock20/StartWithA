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

"""Routes for the corporate action form: new, edit, delete, and the price prefill."""

import logging
from decimal import Decimal, InvalidOperation

from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import Company, CorporateAction, PortfolioPosition
from app.models.portfolio import CORPORATE_ACTION_TYPES, shares_held_on
from app.portfolio import portfolio_bp
from app.services.corporate_action_service import (
    CorporateActionError, CorporateActionInput, CorporateActionService,
)
from app.services.currency_service import CurrencyService
from app.utils.financial_utils import get_historical_price
from app.utils.time_utils import now_utc, parse_date_to_date_object

logger = logging.getLogger(__name__)

TEXT_FIELDS = ('action_type', 'effective_date', 'source_company_id', 'target_company_id',
               'target_ticker', 'shares_received', 'price_per_share', 'cash_received', 'fees',
               'ratio', 'cost_allocation_pct', 'notes', 'sd_shares_received', 'sd_price_per_share',
               'split_ratio')
RECEIVED_LEGS = ('MERGER_IN', 'SPINOFF_CHILD', 'STOCK_DIVIDEND')


def _decimal(form, field, default=None):
    raw = (form.get(field) or '').strip()
    if not raw:
        return default
    try:
        return Decimal(raw)
    except InvalidOperation:
        raise CorporateActionError(f'Invalid number in {field}')


def _whole(form, field):
    value = _decimal(form, field)
    if value is None:
        return None
    if value != value.to_integral_value():
        raise CorporateActionError(f'Invalid number in {field}')
    return int(value)


def _parse_input(form) -> CorporateActionInput:
    """Form -> CorporateActionInput. Raises CorporateActionError with the field name on bad input."""
    effective = parse_date_to_date_object(form.get('effective_date') or '')
    if effective is None:
        raise CorporateActionError('Enter a valid effective date.')
    source_id = _whole(form, 'source_company_id')
    if not source_id:
        raise CorporateActionError('Choose the company you held.')
    kind = form.get('action_type') or ''
    # Each type reads only its own inputs, so a hidden section's stale values can't leak in.
    if kind == 'STOCK_DIVIDEND':
        shares, price, ratio = _whole(form, 'sd_shares_received'), _decimal(form, 'sd_price_per_share'), None
    elif kind == 'SPLIT':
        shares, price, ratio = None, None, _decimal(form, 'split_ratio')
    else:
        shares, price = _whole(form, 'shares_received'), _decimal(form, 'price_per_share')
        ratio = _decimal(form, 'ratio') if kind == 'MERGER' else None
    cash_fees = kind in ('MERGER', 'SPINOFF', 'STOCK_DIVIDEND')
    return CorporateActionInput(
        action_type=kind,
        effective_date=effective,
        source_company_id=source_id,
        target_company_id=_whole(form, 'target_company_id'),
        target_ticker=(form.get('target_ticker') or '').strip() or None,
        shares_received=shares,
        price_per_share=price,
        cash_received=_decimal(form, 'cash_received', Decimal('0')) if cash_fees else Decimal('0'),
        fees=_decimal(form, 'fees', Decimal('0')) if cash_fees else Decimal('0'),
        ratio=ratio,
        cost_allocation_pct=_decimal(form, 'cost_allocation_pct') if kind == 'SPINOFF' else None,
        zero_cost=form.get('zero_cost') == '1',
        notes=(form.get('notes') or '').strip(),
    )


def _fmt(value, places=2):
    return f'{Decimal(value):.{places}f}'


def _received_price(leg) -> str:
    """
    Price per share as entered, rebuilt from the leg's exact base value and stored rate
    (price_per_share keeps 2 decimals, so re-saving it would shift the value).
    """
    rate = Decimal(str(leg.exchange_rate or 0))
    if not leg.quantity or not rate or leg.corporate_value_base is None:
        return _fmt(leg.price_per_share)
    price = (Decimal(str(leg.corporate_value_base)) / leg.quantity / rate).quantize(Decimal('0.000001'))
    if price == price.quantize(Decimal('0.01')):
        return _fmt(price)
    return f'{price.normalize():f}'


def _form_from_action(action: CorporateAction) -> dict:
    """Prefill values for the edit form, from the stored action and its legs."""
    form = {
        'action_type': action.action_type,
        'effective_date': action.effective_date.isoformat(),
        'source_company_id': str(action.source_company_id),
        'target_company_id': str(action.target_company_id or ''),
        'ratio': '', 'split_ratio': '',
        'cost_allocation_pct': '' if action.cost_allocation_pct is None
        else f'{action.cost_allocation_pct.normalize():f}',
        'notes': action.notes or '',
        'zero_cost': '',
    }
    ratio = '' if action.ratio is None else f'{action.ratio.normalize():f}'
    if action.action_type == 'SPLIT':
        form['split_ratio'] = ratio
    elif action.action_type == 'MERGER':
        form['ratio'] = ratio
    if action.action_type in ('STOCK_DIVIDEND', 'SPLIT'):
        form['target_company_id'] = ''
    received = next((leg for leg in action.legs if leg.type in RECEIVED_LEGS), None)
    if received is not None:
        prefix = 'sd_' if action.action_type == 'STOCK_DIVIDEND' else ''
        form[prefix + 'shares_received'] = str(received.quantity)
        form[prefix + 'price_per_share'] = _received_price(received)
        if action.action_type == 'STOCK_DIVIDEND' and received.corporate_value_base == 0:
            form['zero_cost'] = '1'
            form['sd_price_per_share'] = ''
    carrier = next((leg for leg in action.legs if (leg.cash_amount or 0) or (leg.fees or 0)), None)
    form['cash_received'] = _fmt(carrier.cash_amount or 0) if carrier else ''
    form['fees'] = _fmt(carrier.fees or 0) if carrier else ''
    return form


def _company_currency(company: Company) -> str:
    return company.reporting_currency or CurrencyService.detect_currency_from_ticker(company.ticker_symbol)


def _render_form(form, action=None, preview=None, error=None):
    source_id = int(form['source_company_id']) if str(form.get('source_company_id') or '').isdigit() else None
    source = Company.query.filter_by(id=source_id, user_id=current_user.id).first() if source_id else None
    effective = parse_date_to_date_object(form.get('effective_date') or '') or now_utc().date()
    held = (PortfolioPosition.query.filter(PortfolioPosition.user_id == current_user.id,
                                           PortfolioPosition.total_shares > 0)
            .join(Company, Company.id == PortfolioPosition.company_id)
            .order_by(Company.ticker_symbol).with_entities(Company).all())
    companies = Company.query.filter_by(user_id=current_user.id).order_by(Company.ticker_symbol).all()
    return render_template(
        'corporate_action_form.html', form=form, action=action, preview=preview, error=error,
        source=source, held_companies=held, companies=companies,
        currencies={c.id: _company_currency(c) for c in companies},
        source_shares=shares_held_on(source.id, current_user.id, effective) if source else 0,
        action_types=CORPORATE_ACTION_TYPES,
        base_currency=current_user.base_currency,
        base_symbol=CurrencyService.get_currency_symbol(current_user.base_currency),
    )


def _after_save(source_id):
    return redirect(url_for('companies.company_detail', company_id=source_id, _anchor='transactions'))


def _handle(action=None):
    """Shared by new and edit: preview re-renders, save redirects, errors re-render."""
    form = {k: request.form.get(k, '') for k in TEXT_FIELDS}
    form['zero_cost'] = '1' if request.form.get('zero_cost') == '1' else ''
    user = current_user._get_current_object()
    action_id = action.id if action else None
    try:
        data = _parse_input(request.form)
        if request.form.get('intent') == 'save':
            if action:
                CorporateActionService.update(user, action_id, data)
                flash('Corporate action updated.', 'success')
            else:
                CorporateActionService.create(user, data)
                flash('Corporate action recorded.', 'success')
            return _after_save(data.source_company_id)
        preview = CorporateActionService.preview(user, data, action_id)
        return _render_form(form, action, preview=preview)
    except CorporateActionError as exc:
        db.session.rollback()
        return _render_form(form, action, error=str(exc))


@portfolio_bp.route('/corporate-action/new', methods=['GET', 'POST'])
@login_required
def new_corporate_action():
    if request.method == 'POST':
        return _handle()
    form = {k: '' for k in TEXT_FIELDS}
    form.update(action_type='MERGER', effective_date=now_utc().date().isoformat(),
                source_company_id=request.args.get('company_id', ''), zero_cost='')
    return _render_form(form)


def _own_action(action_id) -> CorporateAction:
    action = CorporateAction.query.filter_by(id=action_id, user_id=current_user.id).first()
    if action is None:
        abort(404)
    return action


@portfolio_bp.route('/corporate-action/<int:action_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_corporate_action(action_id):
    action = _own_action(action_id)
    if request.method == 'POST':
        return _handle(action)
    return _render_form(_form_from_action(action), action)


@portfolio_bp.route('/corporate-action/<int:action_id>/delete', methods=['POST'])
@login_required
def delete_corporate_action(action_id):
    action = _own_action(action_id)
    source_id = action.source_company_id
    try:
        CorporateActionService.delete(current_user._get_current_object(), action_id)
        flash('Corporate action deleted.', 'success')
        return _after_save(source_id)
    except CorporateActionError as exc:
        db.session.rollback()
        flash(str(exc), 'error')
        return redirect(url_for('portfolio.edit_corporate_action', action_id=action_id))


@portfolio_bp.route('/corporate-action/price')
@login_required
def corporate_action_price():
    """Closing price for the form's prefill. Null when the lookup fails."""
    ticker = (request.args.get('ticker') or '').strip()
    on = parse_date_to_date_object(request.args.get('date') or '')
    price = None
    if ticker and on:
        try:
            value = get_historical_price(ticker, on)
            price = float(value) if value is not None else None
        except Exception:
            logger.warning('Price lookup failed for %s on %s', ticker, on, exc_info=True)
    return jsonify({'price': price})
