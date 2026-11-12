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

"""How a corporate action shows up afterwards: row fields for the transaction tables and banners for the company page."""

from decimal import Decimal
from typing import Dict, List, Optional

from flask import url_for

from app import db
from app.models import Company, CorporateAction, Transaction
from app.models.portfolio import CORPORATE_LEG_LABELS, CORPORATE_LEG_TYPES, fifo_state_before
from app.services.currency_service import CurrencyService


def row_fields(txn: Transaction, base_currency: str) -> Dict:
    """
    Fields every transactions-table row carries for corporate actions.

    Leg amounts are in the user's base currency (Transaction.total_value), so a
    leg's price and symbol are switched to base too and the number always matches
    its symbol. edit_url is only set for rows that belong to an action.
    """
    fields = {
        'corporate_action_id': txn.corporate_action_id,
        'label': CORPORATE_LEG_LABELS.get(txn.type, txn.type),
    }
    if txn.corporate_action_id is not None:
        fields['edit_url'] = url_for('portfolio.edit_corporate_action', action_id=txn.corporate_action_id)
    if txn.type in CORPORATE_LEG_TYPES:
        fields['currency_symbol'] = CurrencyService.get_currency_symbol(base_currency)
        fields['price'] = float(txn.price_per_share_base if txn.price_per_share_base is not None
                                else txn.price_per_share or 0)
    return fields


def has_corporate_leg(company_id: int, user_id: int) -> bool:
    """Whether a corporate action wrote a leg on the company (its history then stays visible and exportable)."""
    return db.session.query(Transaction.id).filter(
        Transaction.company_id == company_id,
        Transaction.user_id == user_id,
        Transaction.corporate_action_id.isnot(None),
    ).first() is not None


def _merger_gain(action: CorporateAction) -> Optional[Decimal]:
    """
    Realized gain the merger itself produced on the source company: the MERGER_OUT
    proceeds minus the cost the FIFO walk held just before it (it removes every share).
    None when the action has no MERGER_OUT leg (the banner then shows no gain).
    """
    leg = next((t for t in action.legs if t.type == 'MERGER_OUT'), None)
    if leg is None:
        return None
    proceeds = (Decimal(str(leg.corporate_value_base or 0)) + Decimal(str(leg.cash_amount_base or 0))
                - Decimal(str(leg.fees_base if leg.fees_base is not None else leg.fees or 0)))
    return proceeds - fifo_state_before(leg).total_cost


def _banner(prefix: str, other: Company = None, suffix: str = '', icon: str = 'bi-diagram-3',
            action: CorporateAction = None) -> Dict:
    return {'prefix': prefix, 'other': other, 'suffix': suffix, 'icon': icon,
            'edit_url': url_for('portfolio.edit_corporate_action', action_id=action.id) if action else None,
            'gain': None}


def corporate_action_banners(company: Company, user_id: int) -> List[Dict]:
    """
    Banner data for the company page header: one dict per merger or spin-off that
    touches the company. Keys: prefix, other (Company or None), suffix, icon,
    edit_url, gain (Decimal or None; only on a merged-away company).
    """
    banners = []
    actions = CorporateAction.query.filter(
        CorporateAction.user_id == user_id,
        (CorporateAction.source_company_id == company.id) | (CorporateAction.target_company_id == company.id),
    ).order_by(CorporateAction.effective_date).all()
    for action in actions:
        when = action.effective_date.strftime('%d %b %Y')
        if action.action_type == 'MERGER' and action.source_company_id == company.id:
            if action.target_company is not None:
                banner = _banner('Merged into', action.target_company, f'on {when}', action=action)
            else:
                banner = _banner(f'Taken over for cash on {when}', action=action)
            banner['gain'] = _merger_gain(action)
            banners.append(banner)
        elif action.target_company_id == company.id and action.action_type == 'MERGER':
            banners.append(_banner('Includes shares from', action.source_company, f'(merger, {when})', action=action))
        elif action.target_company_id == company.id and action.action_type == 'SPINOFF':
            banners.append(_banner('Spun off from', action.source_company, f'({when})', action=action))
    return banners
