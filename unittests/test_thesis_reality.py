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

"""Thesis vs Reality: status when the expected return or timeframe is missing (#413)."""

from datetime import timedelta

import pytest

from app import db
from app.models import DecisionJournal, ThesisEvolution
from app.models.portfolio import PortfolioPosition
from app.services.portfolio_intelligence import (
    PortfolioIntelligenceService,
    annualize_expected_return,
    expected_return_to_date,
    get_return_target,
)
from app.utils.time_utils import now_utc
from conftest import _make_company, _make_user


def _assess(expected_return, expected_timeframe, annualized_return, total_return, days_held):
    return PortfolioIntelligenceService(user_id=0)._assess_thesis_status(
        expected_return=expected_return,
        expected_timeframe=expected_timeframe,
        annualized_return=annualized_return,
        total_return=total_return,
        days_held=days_held,
    )


# ── expected return maths ──

def test_annualize_converts_total_over_timeframe_to_cagr():
    # 50% over 36 months is ~14.5% a year, not 50% a year
    assert annualize_expected_return(50, 36) == pytest.approx(14.47, abs=0.01)
    assert annualize_expected_return(25, 12) == pytest.approx(25.0)


def test_annualize_without_timeframe_assumes_twelve_months():
    assert annualize_expected_return(25, None) == pytest.approx(25.0)


def test_annualize_without_expected_return_is_none():
    assert annualize_expected_return(None, 12) is None


def test_expected_to_date_is_prorated_by_compounding():
    assert expected_return_to_date(21, 24, 365) == pytest.approx(10.0, abs=0.01)
    assert expected_return_to_date(25, 12, 0) == pytest.approx(0.0)


# ── status when no expected return was recorded ──

@pytest.mark.parametrize('annualized_return', [35.0, 8.0])
def test_no_expected_return_and_gaining_is_no_target(annualized_return):
    # Used to be 'exceeding' / 'on_track' against an invented 20%/0% plan
    assert _assess(None, None, annualized_return, annualized_return, 400) == 'no_target'


def test_no_expected_return_and_small_loss_needs_attention():
    # Used to be 'behind' (a plan that doesn't exist)
    assert _assess(None, None, -4.0, -4.0, 400) == 'needs_attention'


def test_no_expected_return_with_timeframe_is_still_no_target():
    assert _assess(None, 24, 5.0, 5.0, 400) == 'no_target'


# ── status when an expected return was recorded ──

def test_long_horizon_target_compares_cagr_to_annualized_target():
    # 50% over 36 months (~14.5%/yr); 15% CAGR is on track, not "behind" a 50%/yr bar
    assert _assess(50, 36, 15.0, 32.0, 730) == 'on_track'


def test_missing_timeframe_short_hold_uses_prorated_target():
    # 20% expected, no timeframe (12 months assumed), 15 days held: ~0.75% due by now.
    # The old "10% of expected" rule demanded 2%, so 0.8% read as 'behind'.
    assert _assess(20, None, 0.8, 0.8, 15) == 'on_track'


def test_short_hold_with_timeframe_uses_prorated_target():
    # 12% over 12 months, 20 days held: ~0.62% due by now
    assert _assess(12, 12, 0.3, 0.3, 20) == 'behind'
    assert _assess(12, 12, 2.0, 2.0, 20) == 'exceeding'


def test_losing_money_with_target_needs_attention():
    assert _assess(25, 12, -3.0, -3.0, 200) == 'needs_attention'


# ── page and service ──

def _seed_position(user_id, company_id, gain_pct, days_held):
    db.session.add(PortfolioPosition(
        user_id=user_id, company_id=company_id, is_active=True,
        total_shares=10, current_value=1000, unrealized_gain_loss_pct=gain_pct,
        first_purchase_date=now_utc().date() - timedelta(days=days_held)))


def _seed_buy(user_id, company_id, expected_return, expected_timeframe):
    db.session.add(DecisionJournal(
        user_id=user_id, company_id=company_id, decision_type='BUY',
        decision_date=now_utc().date(), is_portfolio_decision=True,
        investment_thesis='Thesis', expected_return=expected_return,
        expected_timeframe=expected_timeframe))


def test_reality_check_without_target_reports_no_target(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _seed_position(user.id, company.id, gain_pct=30, days_held=400)
    _seed_buy(user.id, company.id, expected_return=None, expected_timeframe=None)
    db.session.commit()

    [result] = PortfolioIntelligenceService(user.id).get_thesis_reality_check()

    assert result.status == 'no_target'
    assert result.expected_return is None
    assert result.expected_annualized_return is None


def test_reality_check_with_target_exposes_annualized_target(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _seed_position(user.id, company.id, gain_pct=32, days_held=730)
    _seed_buy(user.id, company.id, expected_return=50, expected_timeframe=36)
    db.session.commit()

    [result] = PortfolioIntelligenceService(user.id).get_thesis_reality_check()

    assert result.status == 'on_track'
    assert result.expected_annualized_return == pytest.approx(14.47, abs=0.01)


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
    _seed_buy(user.id, with_target.id, expected_return=50, expected_timeframe=36)
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
    assert 'No expected return set' in html
    assert 'id="section-ontrack"' in html
    assert '+50.0% over 36mo' in html
    assert '+14.5%' in html
    assert 'id="section-exceeding"' not in html


# ── setting or revising a target through Update Thesis ──

def test_thesis_version_target_overrides_purchase_target(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _seed_position(user.id, company.id, gain_pct=32, days_held=730)
    # Bought expecting 100% in 12 months; later revised to 50% over 36 months
    _seed_buy(user.id, company.id, expected_return=100, expected_timeframe=12)
    _seed_thesis(user.id, company.id, 1, {'expected_return': 50, 'expected_timeframe': 36})
    db.session.commit()

    [result] = PortfolioIntelligenceService(user.id).get_thesis_reality_check()

    assert result.expected_return == 50
    assert result.expected_timeframe_months == 36
    assert result.target_source == 'thesis'
    assert result.target_version == 1
    assert result.status == 'on_track'


def test_thesis_version_target_works_without_a_buy_journal(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _seed_position(user.id, company.id, gain_pct=30, days_held=400)
    _seed_thesis(user.id, company.id, 1, {'expected_return': 25, 'expected_timeframe': 12})
    db.session.commit()

    [result] = PortfolioIntelligenceService(user.id).get_thesis_reality_check()

    assert result.target_source == 'thesis'
    assert result.status != 'no_target'


def test_later_version_without_target_keeps_the_revised_one(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _seed_buy(user.id, company.id, expected_return=100, expected_timeframe=12)
    _seed_thesis(user.id, company.id, 1, {'expected_return': 50, 'expected_timeframe': 36})
    _seed_thesis(user.id, company.id, 2, {'target_price': 120.0})
    db.session.commit()

    target = get_return_target(user.id, company.id)

    assert (target.expected_return, target.source, target.thesis_version) == (50, 'thesis', 1)


def test_purchase_target_is_used_when_no_version_revises_it(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _seed_buy(user.id, company.id, expected_return=20, expected_timeframe=24)
    _seed_thesis(user.id, company.id, 1)
    db.session.commit()

    target = get_return_target(user.id, company.id)

    assert (target.expected_return, target.expected_timeframe_months, target.source) == (20, 24, 'purchase')


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
    assert version.key_metrics == {'expected_return': 40.0, 'expected_timeframe': 24}
    [result] = PortfolioIntelligenceService(user.id).get_thesis_reality_check()
    assert (result.expected_return, result.target_source) == (40.0, 'thesis')


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
    _seed_buy(user.id, company.id, expected_return=25, expected_timeframe=18)
    client = _logged_in(_app, user)

    html = client.get(f'/portfolio/position/{company.id}/thesis/new').get_data(as_text=True)

    assert 'name="expected_return"' in html
    assert 'value="25.0"' in html
    assert 'value="18"' in html
    assert 'Set when you bought.' in html
