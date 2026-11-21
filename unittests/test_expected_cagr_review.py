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

"""Reviewing expected returns saved before they became CAGRs."""

import pytest

from app import db
from app.models import DecisionJournal, ExpectedCagrReview, ThesisEvolution
from app.services.expected_cagr_review import (
    convert_totals,
    keep_values,
    review_entries,
    set_values,
)
from app.services.expected_return import cagr_from_total
from app.utils.time_utils import now_utc
from conftest import _make_company, _make_user


def _buy(user_id, company_id, value, months):
    journal = DecisionJournal(
        user_id=user_id, company_id=company_id, decision_type='BUY',
        decision_date=now_utc().date(), is_portfolio_decision=True,
        investment_thesis='Thesis', expected_cagr=value, expected_timeframe=months)
    db.session.add(journal)
    db.session.flush()
    return journal


def _thesis(user_id, company_id, value, months):
    thesis = ThesisEvolution(
        user_id=user_id, company_id=company_id, version=1, thesis='Thesis',
        change_summary='Update', conviction_level=7, is_current=True,
        key_metrics={'expected_cagr': value, 'expected_timeframe': months, 'target_price': 120})
    db.session.add(thesis)
    db.session.flush()
    return thesis


def _queue(kind, entry, value, months):
    db.session.add(ExpectedCagrReview(kind=kind, entry_id=entry.id, user_id=entry.user_id,
                                      original_value=value, timeframe_months=months))


@pytest.fixture
def queued(app_context):
    user = _make_user()
    company = _make_company(user.id)
    buy = _buy(user.id, company.id, 50, 36)
    thesis = _thesis(user.id, company.id, 40, 24)
    _queue('buy', buy, 50, 36)
    _queue('thesis', thesis, 40, 24)
    db.session.commit()
    return user, buy, thesis


def test_cagr_from_total():
    assert cagr_from_total(50, 36) == pytest.approx(14.47)
    assert cagr_from_total(10, 6) == pytest.approx(21.0)
    assert cagr_from_total(25, 12) == pytest.approx(25.0)


def test_review_lists_open_entries_with_their_cagr_if_total(queued):
    user, buy, thesis = queued

    entries = review_entries(user_id=user.id)

    assert [(e.kind, e.id, e.current_value, e.cagr_if_total) for e in entries] == [
        ('buy', buy.id, 50, 14.47), ('thesis', thesis.id, 40, 18.32)]


def test_convert_stores_the_cagr_and_running_it_again_changes_nothing(queued):
    user, buy, thesis = queued

    convert_totals([('buy', buy.id), ('thesis', thesis.id)])
    [again] = convert_totals([('buy', buy.id)])

    assert again.error is None
    assert db.session.get(DecisionJournal, buy.id).expected_cagr == 14.47
    assert db.session.get(ThesisEvolution, thesis.id).key_metrics == {
        'expected_cagr': 18.32, 'expected_timeframe': 24, 'target_price': 120}
    assert review_entries(user_id=user.id) == []


def test_convert_refuses_a_value_changed_since_the_migration(queued):
    user, buy, _ = queued
    buy.expected_cagr = 18
    db.session.commit()

    [result] = convert_totals([('buy', buy.id)])

    assert 'changed since the migration' in result.error
    assert db.session.get(DecisionJournal, buy.id).expected_cagr == 18


def test_one_failure_writes_nothing(queued):
    _, buy, _ = queued

    results = convert_totals([('buy', buy.id), ('buy', 999999)])

    assert results[1].error == 'not on the review list'
    assert db.session.get(DecisionJournal, buy.id).expected_cagr == 50


def test_keep_leaves_the_value_and_resolves_the_entry(queued):
    user, buy, _ = queued

    keep_values([('buy', buy.id)])

    assert db.session.get(DecisionJournal, buy.id).expected_cagr == 50
    assert [e.kind for e in review_entries(user_id=user.id)] == ['thesis']


def test_set_stores_the_given_cagr(queued):
    _, _, thesis = queued

    set_values([('thesis', thesis.id, 16)])

    assert db.session.get(ThesisEvolution, thesis.id).expected_cagr == 16


def test_dry_run_writes_nothing(queued):
    user, buy, _ = queued

    [result] = convert_totals([('buy', buy.id)], dry_run=True)

    assert result.new == 14.47
    assert db.session.get(DecisionJournal, buy.id).expected_cagr == 50
    assert len(review_entries(user_id=user.id)) == 2
