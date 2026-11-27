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

"""Sell post-mortem pre-fills this sale's return and links this trade's BUY journal (#421)."""

from datetime import date
from decimal import Decimal

import pytest

from app import db
from app.models import DecisionJournal
from app.models.ai_intelligence import ResearchOutcome
from app.models.portfolio import Transaction, find_sale, update_portfolio_position_for_company
from app.services.outcome_tracking import sale_postmortem, sync_outcomes_for_company
from conftest import _make_company, _make_user


def _journal(user_id, company_id, decision_type, on):
    journal = DecisionJournal(
        user_id=user_id, company_id=company_id, decision_type=decision_type,
        decision_date=on, investment_thesis=f'{decision_type} on {on}', is_portfolio_decision=True,
    )
    db.session.add(journal)
    db.session.flush()
    return journal


def _txn(user_id, company_id, txn_type, on, quantity, price, journal=None):
    txn = Transaction(
        user_id=user_id, company_id=company_id, type=txn_type, date=on, quantity=quantity,
        currency='USD', price_per_share=Decimal(str(price)), fees=Decimal('0'),
        decision_journal_id=journal.id if journal else None,
    )
    db.session.add(txn)
    db.session.flush()
    return txn


def _sell(user_id, company_id, on, quantity, price):
    journal = _journal(user_id, company_id, 'SELL', on)
    _txn(user_id, company_id, 'SELL', on, quantity, price, journal)
    return journal


def _finish(user_id, company_id):
    update_portfolio_position_for_company(company_id, user_id)
    sync_outcomes_for_company(user_id, company_id)
    db.session.commit()


@pytest.fixture
def rebought(app_context):
    """Trade 1: 10 @ 100 -> 10 @ 150 (+50%). Trade 2: 10 @ 200 -> 4 @ 220, 6 @ 170."""
    user = _make_user()
    company = _make_company(user.id)
    uid, cid = user.id, company.id

    buy1 = _journal(uid, cid, 'BUY', date(2024, 1, 10))
    _txn(uid, cid, 'BUY', date(2024, 1, 10), 10, 100, buy1)
    sell1 = _sell(uid, cid, date(2024, 6, 1), 10, 150)

    buy2 = _journal(uid, cid, 'BUY', date(2025, 1, 10))
    _txn(uid, cid, 'BUY', date(2025, 1, 10), 10, 200, buy2)
    partial = _sell(uid, cid, date(2025, 3, 1), 4, 220)
    close2 = _sell(uid, cid, date(2025, 9, 1), 6, 170)
    _finish(uid, cid)
    return {
        'user_id': uid, 'buy1': buy1.id, 'buy2': buy2.id,
        'sell1': sell1.id, 'partial': partial.id, 'close2': close2.id,
    }


def _pm(journal_id):
    return sale_postmortem(db.session.get(DecisionJournal, journal_id))


def test_sale_that_closes_first_trade_gets_that_trade_return(rebought):
    pm = _pm(rebought['sell1'])
    assert pm.closed_trade is True
    assert pm.calculated_return == pytest.approx(50.0)
    assert pm.opening_decision.id == rebought['buy1']


def test_partial_sale_gets_return_on_shares_it_sold(rebought):
    pm = _pm(rebought['partial'])
    assert pm.closed_trade is False
    assert pm.calculated_return == pytest.approx(10.0)  # 4 @ 220 against 4 @ 200
    assert pm.opening_decision.id == rebought['buy2']


def test_sale_closing_rebought_trade_ignores_earlier_trade(rebought):
    pm = _pm(rebought['close2'])
    # Trade 2: cost 2000, proceeds 880 + 1020 = 1900 -> -5%. Lifetime would be +11.7%.
    assert pm.closed_trade is True
    assert pm.calculated_return == pytest.approx(-5.0)
    assert pm.opening_decision.id == rebought['buy2']


def test_closed_trade_return_matches_research_outcome(rebought):
    outcome = ResearchOutcome.query.filter_by(
        user_id=rebought['user_id'], exit_date=date(2025, 9, 1)).one()
    assert _pm(rebought['close2']).calculated_return == pytest.approx(outcome.realized_return_pct)


def test_find_sale_reports_matched_cost_and_proceeds(rebought):
    txn = Transaction.query.filter_by(decision_journal_id=rebought['partial']).one()
    trip, sale = find_sale(txn)
    assert trip.opening_transaction.decision_journal_id == rebought['buy2']
    assert sale.sold_cost == Decimal('800')
    assert sale.sell_proceeds == Decimal('880')
    assert [s.transaction.decision_journal_id for s in trip.sales] == [rebought['partial'], rebought['close2']]


def test_sell_journal_without_transaction_has_no_prefill(app_context):
    user = _make_user()
    company = _make_company(user.id)
    journal = _journal(user.id, company.id, 'SELL', date(2025, 1, 1))
    db.session.commit()
    pm = sale_postmortem(journal)
    assert pm.calculated_return is None
    assert pm.opening_decision is None


def test_postmortem_page_prefills_and_saves_to_this_trades_buy_journal(client_logged_in):
    client, uid = client_logged_in
    company = _make_company(uid)
    cid = company.id
    buy1 = _journal(uid, cid, 'BUY', date(2024, 1, 10))
    _txn(uid, cid, 'BUY', date(2024, 1, 10), 10, 100, buy1)
    _sell(uid, cid, date(2024, 6, 1), 10, 150)
    buy2 = _journal(uid, cid, 'BUY', date(2025, 1, 10))
    _txn(uid, cid, 'BUY', date(2025, 1, 10), 10, 200, buy2)
    close2 = _sell(uid, cid, date(2025, 9, 1), 10, 180)
    _finish(uid, cid)
    buy1_id, buy2_id, close2_id = buy1.id, buy2.id, close2.id

    page = client.get(f'/portfolio/sell-postmortem/{close2_id}')
    assert page.status_code == 200
    assert 'value="-10.00"' in page.get_data(as_text=True)

    response = client.post(f'/portfolio/sell-postmortem/{close2_id}', data={
        'sell_reason': 'Thesis broke', 'actual_return': '-10.00', 'lessons_learned': 'Paid too much',
    })
    assert response.status_code == 302
    db.session.expire_all()
    assert db.session.get(DecisionJournal, buy2_id).actual_return == pytest.approx(-10.0)
    assert db.session.get(DecisionJournal, buy2_id).lessons_learned == 'Paid too much'
    assert db.session.get(DecisionJournal, buy1_id).actual_return is None
