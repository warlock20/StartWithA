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

"""Thesis vs Reality: the expected return is a CAGR and is compared with the position's CAGR."""

from datetime import timedelta

import pytest

from app import db
from app.models import DecisionJournal, ThesisEvolution
from app.models.ai_intelligence import ResearchOutcome
from app.models.portfolio import PortfolioPosition, Transaction, update_portfolio_position_for_company
from app.services.outcome_tracking import OutcomeTracker, sync_outcomes_for_company
from app.services.portfolio_intelligence import (
    PortfolioIntelligenceService,
    compare_to_expected_cagr,
    expected_return_to_date,
    get_return_target,
)
from app.utils.time_utils import now_utc
from conftest import _make_company, _make_user


def _assess(expected_cagr, annualized_return, total_return, days_held):
    return PortfolioIntelligenceService(user_id=0)._assess_thesis_status(
        expected_cagr=expected_cagr,
        annualized_return=annualized_return,
        total_return=total_return,
        days_held=days_held,
    )


# ── expected return maths ──

def test_expected_to_date_compounds_the_cagr():
    assert expected_return_to_date(10, 365) == pytest.approx(10.0)
    assert expected_return_to_date(21, 730) == pytest.approx(46.41, abs=0.01)
    assert expected_return_to_date(25, 0) == pytest.approx(0.0)


def test_comparison_uses_the_expected_cagr_as_is():
    comparison = compare_to_expected_cagr(15, total_return=52.09, days_held=1096)
    assert comparison.annualized
    assert comparison.expected == pytest.approx(15.0)
    assert comparison.actual == pytest.approx(15.0, abs=0.05)


def test_short_hold_comparison_uses_totals_to_date():
    comparison = compare_to_expected_cagr(12, total_return=0.3, days_held=20)
    assert not comparison.annualized
    assert comparison.actual == pytest.approx(0.3)
    assert comparison.expected == pytest.approx(0.623, abs=0.001)


# ── status when no expected return was recorded ──

@pytest.mark.parametrize('annualized_return', [35.0, 8.0])
def test_no_expected_cagr_and_gaining_is_no_target(annualized_return):
    # Used to be 'exceeding' / 'on_track' against an invented 20%/0% plan
    assert _assess(None, annualized_return, annualized_return, 400) == 'no_target'


def test_no_expected_cagr_and_small_loss_needs_attention():
    # Used to be 'behind' (a plan that doesn't exist)
    assert _assess(None, -4.0, -4.0, 400) == 'needs_attention'


# ── status when an expected return was recorded ──

def test_expected_cagr_is_not_shrunk_by_the_timeframe():
    # 15% a year expected: a position compounding at 6% a year is behind, not
    # 'exceeding' a 15%-over-36-months target read as ~4.8% a year
    assert _assess(15, 6.0, 19.1, 1096) == 'behind'


@pytest.mark.parametrize('annualized_return, status', [
    (18.0, 'exceeding'), (15.0, 'on_track'), (12.0, 'on_track'), (11.0, 'behind'),
])
def test_cagr_bands_around_the_expected_cagr(annualized_return, status):
    assert _assess(15, annualized_return, 40.0, 730) == status


def test_short_hold_uses_return_due_by_now():
    # 12% a year, 20 days held: ~0.62% due by now
    assert _assess(12, 0.3, 0.3, 20) == 'behind'
    assert _assess(12, 2.0, 2.0, 20) == 'exceeding'


def test_losing_money_with_target_needs_attention():
    assert _assess(25, -3.0, -3.0, 200) == 'needs_attention'


# ── page and service ──

def _seed_position(user_id, company_id, gain_pct, days_held):
    """One purchase of 10 shares at 100, now worth gain_pct more."""
    bought = now_utc().date() - timedelta(days=days_held)
    value = 1000 * (1 + gain_pct / 100)
    db.session.add(Transaction(
        user_id=user_id, company_id=company_id, type='BUY', date=bought,
        quantity=10, price_per_share=100))
    db.session.add(PortfolioPosition(
        user_id=user_id, company_id=company_id, is_active=True,
        total_shares=10, total_cost=1000, current_value=value,
        unrealized_gain_loss=value - 1000, unrealized_gain_loss_pct=gain_pct,
        first_purchase_date=bought))


def _seed_buy(user_id, company_id, expected_cagr, expected_timeframe):
    db.session.add(DecisionJournal(
        user_id=user_id, company_id=company_id, decision_type='BUY',
        decision_date=now_utc().date(), is_portfolio_decision=True,
        investment_thesis='Thesis', expected_cagr=expected_cagr,
        expected_timeframe=expected_timeframe))


def test_reality_check_without_target_reports_no_target(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _seed_position(user.id, company.id, gain_pct=30, days_held=400)
    _seed_buy(user.id, company.id, expected_cagr=None, expected_timeframe=None)
    db.session.commit()

    [result] = PortfolioIntelligenceService(user.id).get_thesis_reality_check()

    assert result.status == 'no_target'
    assert result.expected_cagr is None


def test_reality_check_compares_position_cagr_with_expected_cagr(app_context):
    user = _make_user()
    company = _make_company(user.id)
    # 32% over two years is ~14.9% a year: on track for 15% a year
    _seed_position(user.id, company.id, gain_pct=32, days_held=730)
    _seed_buy(user.id, company.id, expected_cagr=15, expected_timeframe=36)
    db.session.commit()

    [result] = PortfolioIntelligenceService(user.id).get_thesis_reality_check()

    assert result.status == 'on_track'
    assert result.expected_cagr == 15


def _logged_in(app, user):
    user.username = user.username or 'tester'
    db.session.commit()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True
    return client


def _seed_thesis(user_id, company_id, version, key_metrics=None):
    db.session.add(ThesisEvolution(
        user_id=user_id, company_id=company_id, version=version, thesis='Thesis',
        change_summary='Update', conviction_level=7, key_metrics=key_metrics,
        is_current=False))


def test_page_lists_positions_without_target_separately(app_context, _app):
    user = _make_user()
    user.username = 'tester'
    with_target = _make_company(user.id, name='Target Co', ticker='TGT')
    without_target = _make_company(user.id, name='Plain Co', ticker='PLN')
    _seed_position(user.id, with_target.id, gain_pct=32, days_held=730)
    _seed_buy(user.id, with_target.id, expected_cagr=15, expected_timeframe=36)
    _seed_position(user.id, without_target.id, gain_pct=30, days_held=400)
    db.session.commit()
    client = _app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True

    response = client.get('/portfolio/thesis-reality')
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="section-notarget"' in html
    assert 'No expected CAGR set' in html
    assert 'id="section-ontrack"' in html
    assert '+15.0%/yr for 36mo' in html
    assert 'id="section-exceeding"' not in html


# ── setting or revising a target through Update Thesis ──

def test_thesis_version_target_overrides_purchase_target(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _seed_position(user.id, company.id, gain_pct=32, days_held=730)
    # Bought expecting 40% a year; later revised to 15% a year
    _seed_buy(user.id, company.id, expected_cagr=40, expected_timeframe=12)
    _seed_thesis(user.id, company.id, 1, {'expected_cagr': 15, 'expected_timeframe': 36})
    db.session.commit()

    [result] = PortfolioIntelligenceService(user.id).get_thesis_reality_check()

    assert result.expected_cagr == 15
    assert result.expected_timeframe_months == 36
    assert result.target_source == 'thesis'
    assert result.target_version == 1
    assert result.status == 'on_track'


def test_thesis_version_target_works_without_a_buy_journal(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _seed_position(user.id, company.id, gain_pct=30, days_held=400)
    _seed_thesis(user.id, company.id, 1, {'expected_cagr': 25, 'expected_timeframe': 12})
    db.session.commit()

    [result] = PortfolioIntelligenceService(user.id).get_thesis_reality_check()

    assert result.target_source == 'thesis'
    assert result.status != 'no_target'


def test_later_version_without_target_keeps_the_revised_one(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _seed_buy(user.id, company.id, expected_cagr=100, expected_timeframe=12)
    _seed_thesis(user.id, company.id, 1, {'expected_cagr': 50, 'expected_timeframe': 36})
    _seed_thesis(user.id, company.id, 2, {'target_price': 120.0})
    db.session.commit()

    target = get_return_target(user.id, company.id)

    assert (target.expected_cagr, target.source, target.thesis_version) == (50, 'thesis', 1)


def test_purchase_target_is_used_when_no_version_revises_it(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _seed_buy(user.id, company.id, expected_cagr=20, expected_timeframe=24)
    _seed_thesis(user.id, company.id, 1)
    db.session.commit()

    target = get_return_target(user.id, company.id)

    assert (target.expected_cagr, target.expected_timeframe_months, target.source) == (20, 24, 'purchase')


def _thesis_form(**extra):
    form = {'thesis': 'Updated thesis', 'change_summary': 'Set a target', 'conviction_level': '7'}
    form.update(extra)
    return form


def test_update_thesis_saves_the_return_target(app_context, _app):
    user = _make_user()
    company = _make_company(user.id)
    _seed_position(user.id, company.id, gain_pct=30, days_held=400)
    client = _logged_in(_app, user)

    response = client.post(f'/portfolio/position/{company.id}/thesis/new',
                           data=_thesis_form(expected_return='40', expected_timeframe='24'))

    assert response.status_code == 302
    version = ThesisEvolution.query.filter_by(user_id=user.id, company_id=company.id).one()
    assert version.key_metrics == {'expected_cagr': 40.0, 'expected_timeframe': 24}
    [result] = PortfolioIntelligenceService(user.id).get_thesis_reality_check()
    assert (result.expected_cagr, result.target_source) == (40.0, 'thesis')


def test_update_thesis_rejects_timeframe_below_one_month(app_context, _app):
    user = _make_user()
    company = _make_company(user.id)
    client = _logged_in(_app, user)

    client.post(f'/portfolio/position/{company.id}/thesis/new',
                data=_thesis_form(expected_return='40', expected_timeframe='0'))

    assert ThesisEvolution.query.filter_by(user_id=user.id).count() == 0


def test_update_thesis_rejects_timeframe_without_return(app_context, _app):
    user = _make_user()
    company = _make_company(user.id)
    client = _logged_in(_app, user)

    client.post(f'/portfolio/position/{company.id}/thesis/new',
                data=_thesis_form(expected_timeframe='24'))

    assert ThesisEvolution.query.filter_by(user_id=user.id).count() == 0


def test_update_thesis_form_prefills_purchase_target(app_context, _app):
    user = _make_user()
    company = _make_company(user.id)
    _seed_position(user.id, company.id, gain_pct=30, days_held=400)
    _seed_buy(user.id, company.id, expected_cagr=25, expected_timeframe=18)
    client = _logged_in(_app, user)

    html = client.get(f'/portfolio/position/{company.id}/thesis/new').get_data(as_text=True)

    assert 'name="expected_return"' in html
    assert '<option value="cagr" selected>' in html
    assert 'value="25.0"' in html
    assert 'value="18"' in html
    assert 'Set when you bought' in html


# ── company page and outcome accuracy use the same CAGR reading ──

def test_company_page_compares_position_cagr_with_expected_cagr(app_context, _app):
    user = _make_user()
    company = _make_company(user.id)
    company.is_in_portfolio = True
    # 32% over two years is ~14.9% a year against 15% a year expected
    _seed_position(user.id, company.id, gain_pct=32, days_held=730)
    position = PortfolioPosition.query.filter_by(company_id=company.id).one()
    position.average_cost_basis = 100
    position.total_cost_basis = 1000
    position.current_price = 132
    _seed_buy(user.id, company.id, expected_cagr=15, expected_timeframe=36)
    client = _logged_in(_app, user)

    html = client.get(f'/companies/{company.id}').get_data(as_text=True)

    assert 'Expected CAGR: <strong>+15.0%</strong>' in html
    assert 'Actual CAGR' in html
    assert '-0.1pp' in html


def test_thesis_accuracy_compares_realized_cagr_with_expected_cagr():
    outcome = ResearchOutcome(expected_cagr_pct=15, actual_hold_days=1096)
    # 52% over three years is ~15% a year: a perfect call, not 37pp short of 52%
    assert OutcomeTracker()._calculate_thesis_accuracy(outcome, 52.09) == pytest.approx(100, abs=0.5)


def test_decisions_page_compares_closed_position_cagr_up_to_last_sale(app_context, _app):
    user = _make_user()
    company = _make_company(user.id)
    bought = now_utc().date() - timedelta(days=1500)
    # Held three years (1096 days) for 52.2%, ~15.04% a year, then sold 404 days ago
    buy = Transaction(user_id=user.id, company_id=company.id, type='BUY', date=bought,
                      quantity=10, price_per_share=100)
    db.session.add(buy)
    db.session.add(Transaction(
        user_id=user.id, company_id=company.id, type='SELL', date=bought + timedelta(days=1096),
        quantity=10, price_per_share=152.20))
    db.session.flush()
    journal = DecisionJournal(
        user_id=user.id, company_id=company.id, decision_type='BUY', decision_date=bought,
        is_portfolio_decision=True, investment_thesis='Thesis', expected_cagr=15, expected_timeframe=36)
    db.session.add(journal)
    db.session.flush()
    buy.decision_journal_id = journal.id
    update_portfolio_position_for_company(company.id, user.id)
    sync_outcomes_for_company(user.id, company.id)
    db.session.commit()
    client = _logged_in(_app, user)

    html = client.get('/portfolio/analytics/decisions?tab=decision-quality').get_data(as_text=True)

    # Annualized over the 1096 days held, not the 1500 to today, nor the 52% total
    assert 'Expected vs actual' in html
    assert '+15.0%' in html
    assert '1 of 1 met' in html


def test_update_thesis_converts_a_total_to_a_cagr(app_context, _app):
    user = _make_user()
    company = _make_company(user.id)
    client = _logged_in(_app, user)

    client.post(f'/portfolio/position/{company.id}/thesis/new',
                data=_thesis_form(expected_return='50', expected_return_basis='total',
                                  expected_timeframe='36'))

    version = ThesisEvolution.query.filter_by(user_id=user.id, company_id=company.id).one()
    assert version.key_metrics == {'expected_cagr': 14.47, 'expected_timeframe': 36}


def test_update_thesis_rejects_a_total_without_timeframe(app_context, _app):
    user = _make_user()
    company = _make_company(user.id)
    client = _logged_in(_app, user)

    client.post(f'/portfolio/position/{company.id}/thesis/new',
                data=_thesis_form(expected_return='50', expected_return_basis='total'))

    assert ThesisEvolution.query.filter_by(user_id=user.id).count() == 0


# ── conviction (from the current thesis) replaces the purchase-time confidence ──

def test_reality_check_carries_current_thesis_conviction(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _seed_position(user.id, company.id, gain_pct=32, days_held=730)
    db.session.add(DecisionJournal(
        user_id=user.id, company_id=company.id, decision_type='BUY',
        decision_date=now_utc().date(), is_portfolio_decision=True,
        investment_thesis='Thesis', expected_cagr=15, expected_timeframe=36, confidence_score=9))
    _seed_thesis(user.id, company.id, 1)  # conviction 7
    db.session.add(ThesisEvolution(
        user_id=user.id, company_id=company.id, version=2, thesis='Thesis',
        change_summary='Less sure', conviction_level=4, is_current=True))
    db.session.commit()

    [result] = PortfolioIntelligenceService(user.id).get_thesis_reality_check()

    assert result.conviction == 4
    assert not hasattr(result, 'confidence_score')


def test_page_shows_conviction_not_confidence(app_context, _app):
    user = _make_user()
    rated = _make_company(user.id, name='Rated Co', ticker='RTD')
    unrated = _make_company(user.id, name='Unrated Co', ticker='UNR')
    for company in (rated, unrated):
        _seed_position(user.id, company.id, gain_pct=32, days_held=730)
        db.session.add(DecisionJournal(
            user_id=user.id, company_id=company.id, decision_type='BUY',
            decision_date=now_utc().date(), is_portfolio_decision=True,
            investment_thesis='Thesis', expected_cagr=15, expected_timeframe=36, confidence_score=9))
    _seed_thesis(user.id, rated.id, 1)  # conviction 7
    client = _logged_in(_app, user)

    html = client.get('/portfolio/thesis-reality').get_data(as_text=True)

    assert 'Confidence' not in html
    assert '9/10' not in html
    assert '>Conviction</th>' in html
    assert 'tr-conviction tr-conviction--high' in html and '7/10' in html
    assert f'/portfolio/position/{unrated.id}/thesis/new' in html
    assert 'tr-conviction--unrated' in html


def test_hub_top_performer_uses_the_current_holding(app_context, _app):
    user = _make_user()
    user.subscription_tier = 'pro'  # the hub is behind portfolio_intelligence
    rebought = _make_company(user.id, name='Rebought Co', ticker='RBT')
    today = now_utc().date()
    # +50% in 50 days, sold out, re-bought 100 days ago and now down 5%
    for days_ago, type_, price in ((1000, 'BUY', 100), (950, 'SELL', 150), (100, 'BUY', 100)):
        db.session.add(Transaction(user_id=user.id, company_id=rebought.id, type=type_,
                                   date=today - timedelta(days=days_ago), quantity=10, price_per_share=price))
    steady = _make_company(user.id, name='Steady Co', ticker='STD')
    db.session.add(Transaction(user_id=user.id, company_id=steady.id, type='BUY',
                               date=today - timedelta(days=400), quantity=10, price_per_share=100))
    db.session.flush()
    for company, price in ((rebought, 95), (steady, 110)):
        update_portfolio_position_for_company(company.id, user.id)
        PortfolioPosition.query.filter_by(company_id=company.id).one().update_market_data(price)
    client = _logged_in(_app, user)

    html = client.get('/portfolio/intelligence').get_data(as_text=True)

    # Lifetime, RBT is +22.5% (the closed trade) and beat STD (+10%)
    assert 'Top: STD (+10.0%)' in html
