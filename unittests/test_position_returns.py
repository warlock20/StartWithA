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

"""A position's return counts realized gains and dividends, not only the open shares."""

import json
import re
from datetime import timedelta
from decimal import Decimal

import pytest

from app import db
from app.models import DecisionJournal
from app.models.portfolio import PortfolioPosition, Transaction, update_portfolio_position_for_company
from app.services.argos.core import ArgosService
from app.services.intelligence_engine import IntelligenceEngine
from app.services.outcome_tracking import sync_outcomes_for_company
from app.services.portfolio_intelligence import PortfolioIntelligenceService
from app.services.position_returns import position_return
from app.services.similar_mistakes import SimilarMistakesService
from app.utils.financial_utils import calculate_xirr
from app.utils.time_utils import now_utc
from conftest import _make_company, _make_user

TODAY = now_utc().date()


def _txn(user, company, type_, days_ago, quantity, price):
    db.session.add(Transaction(
        user_id=user.id, company_id=company.id, type=type_,
        date=TODAY - timedelta(days=days_ago), quantity=quantity, price_per_share=price))


def _position(user, company, price):
    """Rebuild the position from its transactions, then price it."""
    db.session.flush()
    update_portfolio_position_for_company(company.id, user.id)
    position = PortfolioPosition.query.filter_by(user_id=user.id, company_id=company.id).one()
    if price is not None:
        position.update_market_data(price)
    db.session.commit()
    return position


def _aumann(user, company):
    """260 shares at 11.67 bought 831 days ago, 346 of dividends, now at 12.55 (the reported case)."""
    _txn(user, company, 'BUY', 831, 260, Decimal('11.67'))
    _txn(user, company, 'DIVIDEND', 700, 1, Decimal('173'))
    _txn(user, company, 'DIVIDEND', 330, 1, Decimal('173'))
    return _position(user, company, Decimal('12.55'))


def test_return_counts_dividends_received(app_context):
    user = _make_user()
    company = _make_company(user.id, name='Aumann AG', ticker='AAG.DE')
    position = _aumann(user, company)

    measured = position_return(position)

    # 229 unrealized + 346 dividends on 3034 put in
    assert float(position.unrealized_gain_loss_pct) == pytest.approx(7.55, abs=0.01)
    assert float(measured.total_gain) == pytest.approx(574.8)
    assert measured.total_return_pct == pytest.approx(18.94, abs=0.01)
    # The unrealized-only figure annualized to ~3.3%; with the dividends it is ~8.5%
    # (above the 7.9% lump-sum CAGR because the dividends came back early)
    assert measured.annualized_pct == pytest.approx(8.47, abs=0.01)
    assert measured.days == 831


def test_return_counts_gains_on_shares_already_sold(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _txn(user, company, 'BUY', 730, 100, Decimal('10'))
    _txn(user, company, 'SELL', 365, 50, Decimal('20'))
    position = _position(user, company, Decimal('15'))

    measured = position_return(position)

    # 500 realized on the half sold, 250 unrealized on the half held, on 1000 put in
    assert float(position.unrealized_gain_loss_pct) == pytest.approx(50.0)
    assert float(measured.total_gain) == pytest.approx(750.0)
    assert measured.total_return_pct == pytest.approx(75.0)
    assert measured.annualized_pct == calculate_xirr([
        (TODAY - timedelta(days=730), -1000), (TODAY - timedelta(days=365), 1000), (TODAY, 750)])


def test_total_gain_matches_unrealized_plus_realized(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _txn(user, company, 'BUY', 900, 40, Decimal('50'))
    _txn(user, company, 'BUY', 400, 20, Decimal('70'))
    _txn(user, company, 'DIVIDEND', 300, 60, Decimal('1.25'))
    _txn(user, company, 'SELL', 200, 30, Decimal('65'))
    position = _position(user, company, Decimal('80'))

    measured = position_return(position)

    assert measured.total_gain == position.unrealized_gain_loss + position.realized_gain_loss
    assert float(measured.capital_invested) == pytest.approx(40 * 50 + 20 * 70)


def test_top_up_is_not_annualized_over_the_first_purchase(app_context):
    user = _make_user()
    company = _make_company(user.id)
    # 10 shares held two years, 90 more bought a month ago, flat since
    _txn(user, company, 'BUY', 730, 10, Decimal('100'))
    _txn(user, company, 'BUY', 30, 90, Decimal('121'))
    position = _position(user, company, Decimal('121'))

    measured = position_return(position)

    # Money-weighted: the small early stake earned 10% a year, the top-up nothing;
    # a plain CAGR over 730 days would call the whole 1.9% gain ~0.9% a year
    assert measured.annualized_pct == pytest.approx(calculate_xirr([
        (TODAY - timedelta(days=730), -1000), (TODAY - timedelta(days=30), -10890), (TODAY, 12100)]))
    assert measured.annualized_pct > 5


def test_closed_position_is_measured_to_its_last_sale(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _txn(user, company, 'BUY', 1500, 10, Decimal('100'))
    _txn(user, company, 'SELL', 404, 10, Decimal('121'))
    position = _position(user, company, None)

    measured = position_return(position)

    assert not position.is_active
    assert measured.days == 1096
    assert measured.total_return_pct == pytest.approx(21.0)
    assert measured.annualized_pct == pytest.approx(6.55, abs=0.01)


def test_short_hold_is_not_annualized(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _txn(user, company, 'BUY', 10, 10, Decimal('100'))
    position = _position(user, company, Decimal('105'))

    measured = position_return(position)

    assert measured.total_return_pct == pytest.approx(5.0)
    assert measured.annualized_pct is None


def test_open_position_without_a_price_has_no_return(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _txn(user, company, 'BUY', 100, 10, Decimal('100'))
    position = _position(user, company, None)

    assert position_return(position) is None


# ── pages ──

def _logged_in(app, user):
    user.username = user.username or 'tester'
    db.session.commit()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True
    return client


def test_company_page_cagr_counts_dividends(app_context, _app):
    user = _make_user()
    company = _make_company(user.id, name='Aumann AG', ticker='AAG.DE')
    _aumann(user, company)
    company.is_in_portfolio = True
    PortfolioPosition.query.filter_by(company_id=company.id).one().last_price_update = now_utc()
    client = _logged_in(_app, user)

    html = client.get(f'/companies/{company.id}').get_data(as_text=True)

    tile = re.search(r'id="posReturnValue">\s*([^<]+?)\s*</div>', html).group(1)
    assert tile == '+8.5%'


def test_dashboard_row_counts_realized_gains(app_context, _app):
    user = _make_user()
    company = _make_company(user.id)
    _txn(user, company, 'BUY', 730, 100, Decimal('10'))
    _txn(user, company, 'SELL', 365, 50, Decimal('20'))
    position = _position(user, company, Decimal('15'))
    position.last_price_update = now_utc()
    client = _logged_in(_app, user)

    html = client.get('/portfolio/').get_data(as_text=True)

    row = json.loads(re.search(r'var holdingsData = (\[.*?\]);', html).group(1))[0]
    assert (row['gain_loss'], row['gain_loss_pct']) == (750.0, 75.0)


def test_thesis_reality_counts_dividends(app_context):
    user = _make_user()
    company = _make_company(user.id, name='Aumann AG', ticker='AAG.DE')
    _aumann(user, company)
    db.session.add(DecisionJournal(
        user_id=user.id, company_id=company.id, decision_type='BUY',
        decision_date=TODAY - timedelta(days=831), is_portfolio_decision=True,
        investment_thesis='Thesis', expected_cagr=8, expected_timeframe=36))
    db.session.commit()

    [result] = PortfolioIntelligenceService(user.id).get_thesis_reality_check()

    # 8.5% a year against 8% expected; unrealized only (3.3%) read as 'behind'
    assert result.annualized_return_pct == pytest.approx(8.47, abs=0.01)
    assert result.status == 'on_track'


def test_decisions_and_intelligence_pages_use_the_trade_return(app_context, _app):
    user = _make_user()
    company = _make_company(user.id, name='Aumann AG', ticker='AAG.DE')
    _aumann(user, company)
    sync_outcomes_for_company(user.id, company.id)
    db.session.add(DecisionJournal(
        user_id=user.id, company_id=company.id, decision_type='BUY',
        decision_date=TODAY - timedelta(days=831), is_portfolio_decision=True,
        investment_thesis='Thesis', expected_cagr=8, expected_timeframe=36, confidence_score=7))
    client = _logged_in(_app, user)

    decisions = client.get('/portfolio/analytics/decisions')
    hub = client.get('/portfolio/intelligence')

    assert decisions.status_code == hub.status_code == 200
    html = decisions.get_data(as_text=True)
    assert '1 of 1 positions' in html  # 8.5% a year meets the 8% expected
    # the unresearched trade's return if sold now (12.55 on 11.67), leaving dividends out
    assert '+7.5%' in html


def _sold_half_at_four_times(user, company):
    """Bought 100 at 10 400 days ago, sold half at 40 200 days ago; the rest is flat at 10."""
    _txn(user, company, 'BUY', 400, 100, Decimal('10'))
    _txn(user, company, 'SELL', 200, 50, Decimal('40'))
    return _position(user, company, Decimal('10'))


def test_intelligence_hub_top_performer_counts_dividends(app_context, _app):
    user = _make_user()
    aumann = _make_company(user.id, name='Aumann AG', ticker='AAG.DE')
    _aumann(user, aumann)
    other = _make_company(user.id, name='Plain Co', ticker='PLN')
    _txn(user, other, 'BUY', 400, 10, Decimal('100'))
    _position(user, other, Decimal('115'))
    client = _logged_in(_app, user)

    html = client.get('/portfolio/intelligence').get_data(as_text=True)

    # Unrealized only, PLN (+15%) beat AAG.DE (+7.6%); with dividends AAG.DE is +18.9%
    assert 'Top: AAG.DE (+18.9%)' in html


def test_hot_position_warning_counts_gains_already_taken(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _sold_half_at_four_times(user, company)

    warning = IntelligenceEngine(user.id)._check_chasing_returns(company, 1000)

    # The open half is flat (0% unrealized), but the position has made 150% in 400 days
    assert warning is not None
    assert warning.data['total_return'] == pytest.approx(150.0)
    assert warning.data['cagr'] > 50


def test_argos_company_context_carries_the_lifetime_return(app_context):
    user = _make_user()
    company = _make_company(user.id, name='Aumann AG', ticker='AAG.DE')
    _aumann(user, company)

    position = ArgosService(user.id).build_company_context(company.id).to_summary()['position']

    assert position['total_return_pct'] == pytest.approx(18.9)
    assert position['annualized_return_pct'] == pytest.approx(8.5)
    assert position['unrealized_pct'] == pytest.approx(7.55, abs=0.01)


def test_similar_decision_outcome_uses_the_lifetime_return(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _sold_half_at_four_times(user, company)
    decision = DecisionJournal(
        user_id=user.id, company_id=company.id, decision_type='BUY',
        decision_date=TODAY - timedelta(days=400), is_portfolio_decision=True,
        investment_thesis='Thesis')
    db.session.add(decision)
    db.session.commit()

    outcome = SimilarMistakesService(user.id)._get_decision_outcome(decision)

    assert outcome['return_pct'] == pytest.approx(150.0)
    assert outcome['holding_days'] == 400
    assert outcome['is_open']
