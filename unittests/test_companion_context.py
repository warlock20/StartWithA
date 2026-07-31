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

"""Context chips — the rail shows what an answer is grounded on (#311 State C).

Pages declare their own chips from objects they already render; this helper only
normalises that declaration, adds the counts a template can't cheaply compute, and
supplies the account-wide default. The payload stays a *generic* list on purpose:
a page that later declares more produces more chips with no change to the rail.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import render_template
from flask_login import login_user

from app import db
from app.models.journal import JournalEntry
from app.models.user import User
from app.services.argos.page_context import build_context_chips

TEMPLATES = {
    'company': '../app/companies/templates/company_detail.html',
    'portfolio': '../app/portfolio/templates/portfolio_dashboard.html',
    'research': '../app/research_workflow/templates/execute_step.html',
    'kill': '../app/research_workflow/templates/execute_kill_checklist_step.html',
    'free': '../app/research_workflow/templates/free_research_step.html',
}


def _labels(chips):
    return [c['label'] for c in chips]


def test_chips_are_a_generic_list_of_icon_label_kind(seed_company_with_findings):
    """Every chip has the same three keys — no entity-shaped fields."""
    user_id, company_id = seed_company_with_findings
    chips = build_context_chips(user_id, {
        'type': 'company', 'company_id': company_id,
        'chips': [{'icon': 'bi-building', 'label': 'ASML', 'kind': 'mine'}],
    })

    assert chips, 'expected at least one chip'
    for chip in chips:
        assert set(chip) == {'icon', 'label', 'kind'}
        assert chip['kind'] in ('mine', 'page')
        assert isinstance(chip['label'], str) and chip['label']


def test_declared_chips_are_passed_through_in_order(seed_company_with_findings):
    user_id, company_id = seed_company_with_findings
    chips = build_context_chips(user_id, {
        'type': 'company', 'company_id': company_id,
        'chips': [{'icon': 'bi-building', 'label': 'ASML'},
                  {'icon': 'bi-signpost', 'label': 'Durable moat'}],
    })
    assert _labels(chips)[:2] == ['ASML', 'Durable moat']


def test_declared_chips_without_a_label_are_dropped(seed_company_with_findings):
    """A template rendering a missing attribute must not produce an empty chip."""
    user_id, company_id = seed_company_with_findings
    chips = build_context_chips(user_id, {
        'type': 'company', 'company_id': company_id,
        'chips': [{'icon': 'bi-building', 'label': ''},
                  {'icon': 'bi-signpost'},
                  {'icon': 'bi-list-check', 'label': 'Kept'}],
    })
    assert _labels(chips) == ['Kept']


def test_note_count_chip_is_added_for_a_company(seed_company_with_findings):
    """The count is the one thing a template can't cheaply compute itself."""
    user_id, company_id = seed_company_with_findings
    for title in ('n1', 'n2'):
        db.session.add(JournalEntry(
            user_id=user_id, company_id=company_id, title=title,
            entry_type='observation', content='x'))
    db.session.commit()

    chips = build_context_chips(user_id, {'type': 'company', 'company_id': company_id})
    assert any('2 notes' in label for label in _labels(chips))


def test_note_count_is_scoped_to_the_user(seed_company_with_findings, other_user):
    """Counting is filtered by user_id, so a stale id can only ever count your own."""
    user_id, company_id = seed_company_with_findings
    db.session.add(JournalEntry(
        user_id=other_user, company_id=company_id, title='theirs',
        entry_type='observation', content='x'))
    db.session.commit()

    chips = build_context_chips(user_id, {'type': 'company', 'company_id': company_id})
    assert not any('note' in label for label in _labels(chips))


def test_portfolio_focus_counts_holdings(seed_portfolio):
    chips = build_context_chips(seed_portfolio, {'type': 'portfolio'})
    assert any('2 holdings' in label for label in _labels(chips))


def test_empty_focus_falls_back_to_the_account(seed_portfolio):
    """An undeclared page says so honestly rather than inventing a page identity."""
    chips = build_context_chips(seed_portfolio, {})
    assert _labels(chips) == ['Your account']


def test_widget_renders_the_chip_strip(app_context, _app):
    """Chips are server-rendered into the markup — no fetch, no empty-strip flash."""
    user = User(email='chips@example.com')
    db.session.add(user)
    db.session.commit()
    with _app.test_request_context('/'):
        login_user(user)
        html = render_template(
            'main/_companion_widget.html',
            companion_focus={'type': 'company',
                             'chips': [{'icon': 'bi-building', 'label': 'ASML'}]})
    assert 'companion-rail-context' in html
    assert 'ASML' in html


def test_focused_templates_declare_their_chips():
    """The five pages that declare a focus also declare what they're showing."""
    here = os.path.dirname(__file__)
    for name, rel in TEMPLATES.items():
        html = open(os.path.join(here, rel), encoding='utf-8').read()
        assert "'chips'" in html, f'{name} declares a focus but no chips'
