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

"""Knowledge Hub company navigation (#354)."""

import html
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import timedelta

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import db
from app.journal_enhanced.utils import (companies_with_notes, conviction_sparkline,
                                        get_company_knowledge_summary)
from app.models import JournalEntry, LearningNote, MistakeLog, ThesisEvolution
from app.utils.time_utils import now_utc

from conftest import _make_company, _make_user


def _research(user_id, company_id, created_days_ago=0, **kwargs):
    entry = JournalEntry(user_id=user_id, company_id=company_id,
                         content=kwargs.pop('content', 'note'),
                         created_at=now_utc() - timedelta(days=created_days_ago),
                         **kwargs)
    db.session.add(entry)
    db.session.flush()
    return entry


def _wisdom(user_id, company_id, **kwargs):
    note = LearningNote(user_id=user_id, company_id=company_id,
                        title=kwargs.pop('title', 'lesson'), lesson='lesson', **kwargs)
    db.session.add(note)
    db.session.flush()
    return note


def _mistake(user_id, company_id, severity=5, **kwargs):
    mistake = MistakeLog(user_id=user_id, company_id=company_id,
                         title=kwargs.pop('title', 'mistake'), description='d',
                         mistake_type='timing', lesson_learned='l', severity=severity,
                         **kwargs)
    db.session.add(mistake)
    db.session.flush()
    return mistake


def _client_for(app, user):
    # The page chrome renders the username's initials.
    user.username = user.username or 'tester'
    db.session.commit()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True
    return client


# ── companies_with_notes ──

def test_companies_without_notes_are_excluded(app_context):
    user = _make_user()
    noted = _make_company(user.id, 'Noted Co', 'NOTE')
    _make_company(user.id, 'Empty Co', 'EMPT')
    _research(user.id, noted.id)

    companies = companies_with_notes(user.id)

    assert [c.name for c in companies] == ['Noted Co']


def test_counts_are_per_type(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _research(user.id, company.id)
    _research(user.id, company.id)
    _wisdom(user.id, company.id)
    _mistake(user.id, company.id)

    [counts] = companies_with_notes(user.id)

    assert (counts.research, counts.wisdom, counts.mistake, counts.total) == (2, 1, 1, 4)


def test_archived_research_does_not_count(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _research(user.id, company.id, is_archived=True)

    assert companies_with_notes(user.id) == []


def test_companies_are_sorted_by_name_case_insensitively(app_context):
    user = _make_user()
    for name, ticker in [('zeta', 'Z'), ('Alpha', 'A'), ('beta', 'B')]:
        _wisdom(user.id, _make_company(user.id, name, ticker).id)

    assert [c.name for c in companies_with_notes(user.id)] == ['Alpha', 'beta', 'zeta']


def test_other_users_notes_and_companies_are_isolated(app_context):
    me = _make_user('me@example.com')
    other = _make_user('other@example.com')
    their_company = _make_company(other.id, 'Theirs', 'THRS')
    _research(other.id, their_company.id)
    # My note pointing at their company must not surface it to me.
    _research(me.id, their_company.id)

    assert companies_with_notes(me.id) == []
    assert [c.research for c in companies_with_notes(other.id)] == [1]


# ── get_company_knowledge_summary ──

def test_summary_is_none_for_another_users_company(app_context):
    me = _make_user('me@example.com')
    other = _make_user('other@example.com')
    company = _make_company(other.id)

    assert get_company_knowledge_summary(me.id, company.id) is None


def test_summary_for_company_without_notes(app_context):
    user = _make_user()
    company = _make_company(user.id)

    summary = get_company_knowledge_summary(user.id, company.id)

    assert summary['counts'].total == 0
    assert summary['first_note_at'] is None
    assert summary['current_thesis'] is None
    assert summary['conviction_sparkline'] is None


def test_summary_collects_latest_research_signals(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _research(user.id, company.id, created_days_ago=10, sentiment='bearish',
              conviction_level=3, key_insight='old insight',
              questions_raised=['old question'])
    _research(user.id, company.id, created_days_ago=1, sentiment='bullish',
              conviction_level=8, key_insight='new insight',
              questions_raised=['new question', ''], action_items=['call IR'])
    _research(user.id, company.id, created_days_ago=0)  # no signals at all

    summary = get_company_knowledge_summary(user.id, company.id)

    assert summary['latest_sentiment'] == 'bullish'
    assert summary['latest_conviction'] == 8
    assert [e.key_insight for e in summary['key_insights']] == ['new insight', 'old insight']
    assert [q for q, _ in summary['questions_raised']] == ['new question', 'old question']
    assert [a for a, _ in summary['action_items']] == ['call IR']
    assert [c for _, c in summary['conviction_points']] == [3, 8]
    assert summary['conviction_sparkline'] is not None


def test_summary_limits_key_insights(app_context):
    user = _make_user()
    company = _make_company(user.id)
    for i in range(8):
        _research(user.id, company.id, created_days_ago=i, key_insight=f'insight {i}')

    summary = get_company_knowledge_summary(user.id, company.id)

    assert [e.key_insight for e in summary['key_insights']] == [f'insight {i}' for i in range(5)]


def test_summary_prefers_the_current_thesis(app_context):
    user = _make_user()
    company = _make_company(user.id)
    db.session.add_all([
        ThesisEvolution(user_id=user.id, company_id=company.id, version=1,
                        thesis='v1', is_current=True,
                        created_at=now_utc() - timedelta(days=5)),
        ThesisEvolution(user_id=user.id, company_id=company.id, version=2,
                        thesis='v2 draft', is_current=False, created_at=now_utc()),
    ])
    db.session.flush()

    summary = get_company_knowledge_summary(user.id, company.id)

    assert summary['current_thesis'].version == 1


def test_summary_averages_mistake_severity(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _mistake(user.id, company.id, severity=4)
    _mistake(user.id, company.id, severity=7)

    summary = get_company_knowledge_summary(user.id, company.id)

    assert summary['mistake_avg_severity'] == 5.5
    assert summary['counts'].mistake == 2


# ── conviction_sparkline ──

def test_sparkline_needs_two_points():
    assert conviction_sparkline([]) is None
    assert conviction_sparkline([(None, 5)]) is None


def test_sparkline_maps_scale_ends_to_bottom_and_top():
    coords = conviction_sparkline([(None, 1), (None, 10)], width=120, height=28, pad=3)

    assert coords == '3.0,25.0 117.0,3.0'


# ── /journal/knowledge-hub ──

def test_dropdown_lists_only_companies_with_notes(_app, app_context):
    user = _make_user()
    noted = _make_company(user.id, 'Noted Co', 'NOTE')
    _make_company(user.id, 'Empty Co', 'EMPT')
    _research(user.id, noted.id)
    db.session.commit()

    html = _client_for(_app, user).get('/journal/knowledge-hub?type=all').get_data(as_text=True)

    assert 'Noted Co (1)' in html
    assert 'Empty Co' not in html
    assert 'cc-company-name' not in html  # no company selected → no header


def test_company_filter_shows_summary_grouped_by_type(_app, app_context):
    user = _make_user()
    company = _make_company(user.id, 'Noted Co', 'NOTE')
    _research(user.id, company.id, title='A research note', key_insight='moat widening')
    _mistake(user.id, company.id, title='A mistake')
    db.session.commit()

    html = _client_for(_app, user).get(
        f'/journal/knowledge-hub?type=all&company_id={company.id}').get_data(as_text=True)

    assert 'cc-company-name' in html
    assert 'moat widening' in html
    assert 'cc-group-label">Research<' in html
    assert 'cc-group-label">Mistakes<' in html
    assert 'This Week' not in html  # grouped by type, not date


def test_note_title_is_escaped_in_the_page(_app, app_context):
    user = _make_user()
    company = _make_company(user.id)
    _research(user.id, company.id, title='<script>alert(1)</script>')
    db.session.commit()

    html = _client_for(_app, user).get('/journal/knowledge-hub?type=all').get_data(as_text=True)

    assert '<script>alert(1)</script>' not in html


# Runs the page's own inline script with just enough of a DOM for showDetail():
# the card it looks up carries the dataset decoded from the rendered HTML.
_SHOW_DETAIL_HARNESS = r"""
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const elements = {};
const element = id => elements[id] || (elements[id] = {
    innerHTML: '', classList: {add() {}, remove() {}}, addEventListener() {}, focus() {},
});
const card = {dataset: input.dataset};
global.document = {addEventListener() {}, getElementById: element, querySelector: () => card};
global.window = {location: {href: 'http://localhost/'}};
eval(input.script);
showDetail(input.dataset.type, Number(input.dataset.itemId.split('-')[1]));
process.stdout.write(JSON.stringify({
    header: element('ccDetailHeader').innerHTML,
    body: element('ccDetailBody').innerHTML,
}));
"""


def _browser_dataset(card_html):
    """data-* attributes as the browser exposes them: HTML-decoded, camelCased."""
    return {
        re.sub(r'-(\w)', lambda m: m.group(1).upper(), name): html.unescape(value)
        for name, value in re.findall(r'data-([\w-]+)="([^"]*)"', card_html)
    }


@pytest.mark.skipif(shutil.which('node') is None, reason='needs Node.js to run the page script')
def test_detail_panel_escapes_note_values(_app, app_context):
    user = _make_user()
    company = _make_company(user.id, '<b onmouseover=alert(2)>Evil</b> Co', 'EVIL')
    _research(user.id, company.id, title='<img src=x onerror=alert(1)>',
              tags=['<i>tag</i>'])
    db.session.commit()

    page = _client_for(_app, user).get('/journal/knowledge-hub?type=all').get_data(as_text=True)
    card_html = re.search(r'<div class="cc-card"(.*?)onclick=', page, re.S).group(1)
    script = next(block for block in re.findall(r'<script>(.*?)</script>', page, re.S)
                  if 'function showDetail' in block)

    result = subprocess.run(
        ['node', '-e', _SHOW_DETAIL_HARNESS],
        input=json.dumps({'script': script, 'dataset': _browser_dataset(card_html)}),
        capture_output=True, text=True, check=True, timeout=30)
    rendered = json.loads(result.stdout)
    panel = rendered['header'] + rendered['body']

    for raw in ('<img', '<b ', '<i>'):
        assert raw not in panel
    assert '&lt;img src=x onerror=alert(1)&gt;' in rendered['header']
    assert '&lt;b onmouseover=alert(2)&gt;Evil&lt;/b&gt; Co' in rendered['header']
    assert '&lt;i&gt;tag&lt;/i&gt;' in rendered['body']


def test_tab_links_encode_the_search_query(_app, app_context):
    user = _make_user()
    db.session.commit()

    html = _client_for(_app, user).get(
        '/journal/knowledge-hub?type=all&q=R%26D').get_data(as_text=True)

    assert 'q=R%26D' in html
    assert 'q=R&D' not in html and 'q=R&amp;D' not in html


def test_search_matches_company_name(_app, app_context):
    user = _make_user()
    company = _make_company(user.id, 'Hermes International', 'RMS')
    _research(user.id, company.id, title='Pricing power note')
    db.session.commit()

    html = _client_for(_app, user).get(
        '/journal/knowledge-hub?type=all&q=hermes').get_data(as_text=True)

    assert 'Pricing power note' in html


def test_tab_counts_follow_the_company_filter(_app, app_context):
    user = _make_user()
    selected = _make_company(user.id, 'Selected Co', 'SEL')
    other = _make_company(user.id, 'Other Co', 'OTH')
    _research(user.id, selected.id)
    _wisdom(user.id, selected.id)
    _research(user.id, other.id)
    _mistake(user.id, other.id)
    db.session.commit()
    client = _client_for(_app, user)

    scoped = client.get(
        f'/journal/knowledge-hub?type=all&company_id={selected.id}').get_data(as_text=True)
    unscoped = client.get('/journal/knowledge-hub?type=all').get_data(as_text=True)

    def tab_counts(html):
        return re.findall(r'<span class="cc-tab-count">(\d+)</span>', html)

    assert tab_counts(scoped) == ['2', '1', '1', '0']    # all, research, wisdom, mistakes
    assert tab_counts(unscoped) == ['4', '2', '1', '1']


# ── Thesis updates: one conviction point, linked records ──

def _thesis(user_id, company_id, conviction, created_at, version=1, **kwargs):
    thesis = ThesisEvolution(user_id=user_id, company_id=company_id, version=version,
                             thesis='thesis', conviction_level=conviction,
                             created_at=created_at, **kwargs)
    db.session.add(thesis)
    db.session.flush()
    return thesis


def test_linked_thesis_update_note_is_plotted_once(app_context):
    user = _make_user()
    company = _make_company(user.id)
    saved_at = now_utc() - timedelta(days=3)
    note = _research(user.id, company.id, created_days_ago=3, entry_type='thesis_update',
                     conviction_level=7)
    _thesis(user.id, company.id, 7, saved_at, linked_journal_entry_id=note.id)
    _research(user.id, company.id, created_days_ago=1, conviction_level=8)

    summary = get_company_knowledge_summary(user.id, company.id)

    assert [c for _, c in summary['conviction_points']] == [7, 8]


def test_unlinked_legacy_thesis_update_note_is_plotted_once(app_context):
    """Rows saved before the link was stored: matched on conviction and time."""
    user = _make_user()
    company = _make_company(user.id)
    saved_at = now_utc() - timedelta(days=3)
    _thesis(user.id, company.id, 6, saved_at)
    note = _research(user.id, company.id, entry_type='thesis_update', conviction_level=6)
    note.created_at = saved_at + timedelta(seconds=2)
    db.session.flush()

    summary = get_company_knowledge_summary(user.id, company.id)

    assert [c for _, c in summary['conviction_points']] == [6]


def test_thesis_update_note_without_matching_version_is_kept(app_context):
    user = _make_user()
    company = _make_company(user.id)
    _thesis(user.id, company.id, 5, now_utc() - timedelta(days=10))
    _research(user.id, company.id, created_days_ago=2, entry_type='thesis_update',
              conviction_level=5)

    summary = get_company_knowledge_summary(user.id, company.id)

    assert [c for _, c in summary['conviction_points']] == [5, 5]


def test_old_thesis_form_redirects_to_the_portfolio_thesis_form(_app, app_context):
    """Thesis versions are created only on the portfolio thesis form (#356)."""
    user = _make_user()
    company = _make_company(user.id)
    db.session.commit()

    resp = _client_for(_app, user).get(f'/journal/thesis-evolution/{company.id}/new')

    assert resp.status_code == 302
    assert f'/portfolio/position/{company.id}/thesis/new' in resp.headers['Location']


# ── Company header ──

def test_clearing_the_company_keeps_the_other_filters(_app, app_context):
    user = _make_user()
    company = _make_company(user.id)
    _research(user.id, company.id, title='moat note', tags=['moat'], is_starred=True)
    db.session.commit()

    html = _client_for(_app, user).get(
        f'/journal/knowledge-hub?type=research&company_id={company.id}'
        '&q=moat&tag=moat&starred=1&sort=title').get_data(as_text=True)

    clear_href = re.search(r'<a href="([^"]+)"\s+class="cc-company-clear"', html).group(1)
    assert 'company_id' not in clear_href
    for param in ('type=research', 'q=moat', 'tag=moat', 'starred=1', 'sort=title'):
        assert param in clear_href


def test_search_works_with_company_and_starred_filters(_app, app_context):
    """filter_by() after the company join used to target Company and crash."""
    user = _make_user()
    company = _make_company(user.id)
    _research(user.id, company.id, title='moat research', is_starred=True)
    _wisdom(user.id, company.id, title='moat wisdom', is_favorite=True)
    _mistake(user.id, company.id, title='moat mistake')
    db.session.commit()

    resp = _client_for(_app, user).get(
        f'/journal/knowledge-hub?type=all&company_id={company.id}&q=moat&starred=1')

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'moat research' in html and 'moat wisdom' in html


def test_search_joins_company_once_per_note_query(_app, app_context):
    """The company join used for search also eager-loads the company."""
    from sqlalchemy import event

    user = _make_user()
    company = _make_company(user.id, 'Hermes International', 'RMS')
    _research(user.id, company.id, title='Pricing power note')
    db.session.commit()
    client = _client_for(_app, user)

    statements = []

    def capture(conn, cursor, statement, *args):
        statements.append(statement)

    event.listen(db.engine, 'before_cursor_execute', capture)
    try:
        html_page = client.get('/journal/knowledge-hub?type=all&q=hermes').get_data(as_text=True)
    finally:
        event.remove(db.engine, 'before_cursor_execute', capture)

    assert 'Pricing power note' in html_page
    note_queries = [s for s in statements
                    if re.search(r'FROM (journal_entry|learning_note|mistake_log)\b', s)
                    and 'ILIKE' in s.upper()]
    assert len(note_queries) == 3
    for statement in note_queries:
        assert len(re.findall(r'JOIN company\b', statement)) == 1, statement
