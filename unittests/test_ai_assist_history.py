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

"""GET /research/workflow/ai_assist/history/<analysis_id>/<item_id>.

Responses were always persisted to ai_research_feedback, but nothing could read
them back, so switching between Fact-Check and Elaboration silently discarded
the previous result. These cover the read path.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import datetime

from app import db
from app.models import (AIResearchFeedback, Checklist, ChecklistAnalysis,
                        ChecklistItem, Company, User)


def _seed(user_id, answer='the original answer'):
    """A checklist analysis with one item, owned by user_id."""
    company = Company(name='Copart', ticker_symbol='CPRT', user_id=user_id)
    checklist = Checklist(name='Moat', user_id=user_id)
    db.session.add_all([company, checklist])
    db.session.flush()

    item = ChecklistItem(text='What is the moat?', checklist_id=checklist.id)
    analysis = ChecklistAnalysis(
        user_id=user_id, company_id=company.id, checklist_id=checklist.id,
        start_date=datetime.date.today(), status='in_progress')
    db.session.add_all([item, analysis])
    db.session.flush()
    return analysis, item


def _feedback(user_id, analysis, item, mode, response, answer='the original answer', **kw):
    row = AIResearchFeedback(
        user_id=user_id, analysis_id=analysis.id, item_id=item.id,
        mode=mode, question_text='Q', user_answer=answer,
        ai_response=response, **kw)
    db.session.add(row)
    db.session.flush()
    return row


def test_returns_latest_response_per_mode(client_logged_in):
    client, uid = client_logged_in
    analysis, item = _seed(uid)
    _feedback(uid, analysis, item, 'factcheck', 'fact one')
    _feedback(uid, analysis, item, 'elaboration', 'elaborate one')
    db.session.commit()

    resp = client.get(f'/research/workflow/ai_assist/history/{analysis.id}/{item.id}')

    assert resp.status_code == 200
    data = resp.get_json()['responses']
    assert data['factcheck']['response'] == 'fact one'
    assert data['elaboration']['response'] == 'elaborate one'
    # The stored answer comes back so the client can tell whether it is stale.
    assert data['factcheck']['user_answer'] == 'the original answer'


def test_returns_only_the_newest_per_mode(client_logged_in):
    client, uid = client_logged_in
    analysis, item = _seed(uid)
    older = _feedback(uid, analysis, item, 'factcheck', 'stale')
    newer = _feedback(uid, analysis, item, 'factcheck', 'fresh')
    older.created_at = datetime.datetime(2020, 1, 1)
    newer.created_at = datetime.datetime(2026, 1, 1)
    db.session.commit()

    resp = client.get(f'/research/workflow/ai_assist/history/{analysis.id}/{item.id}')

    assert resp.get_json()['responses']['factcheck']['response'] == 'fresh'


def test_omits_dismissed_and_anonymized_responses(client_logged_in):
    client, uid = client_logged_in
    analysis, item = _seed(uid)
    # Explicitly dismissed by the user — restoring it would be unwelcome.
    _feedback(uid, analysis, item, 'challenge', 'dismissed one', feedback='dismissed')
    # GDPR retention blanks old text; there is nothing useful to restore.
    _feedback(uid, analysis, item, 'factcheck', '[anonymized]')
    db.session.commit()

    resp = client.get(f'/research/workflow/ai_assist/history/{analysis.id}/{item.id}')

    assert resp.get_json()['responses'] == {}


def test_denies_another_users_analysis(client_logged_in):
    client, _uid = client_logged_in
    other = User(email='foreign@example.com')
    db.session.add(other)
    db.session.flush()
    analysis, item = _seed(other.id)
    _feedback(other.id, analysis, item, 'factcheck', 'private')
    db.session.commit()

    resp = client.get(f'/research/workflow/ai_assist/history/{analysis.id}/{item.id}')

    assert resp.status_code == 403
    assert 'private' not in resp.get_data(as_text=True)


def test_empty_when_nothing_stored(client_logged_in):
    client, uid = client_logged_in
    analysis, item = _seed(uid)
    db.session.commit()

    resp = client.get(f'/research/workflow/ai_assist/history/{analysis.id}/{item.id}')

    assert resp.status_code == 200
    assert resp.get_json()['responses'] == {}
