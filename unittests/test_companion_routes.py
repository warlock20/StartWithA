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

"""The /companion blueprint: ask, capture, warnings (Task 13). DB-backed."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json

import app.companion.routes as companion_routes
from app import db
from app.models.journal import JournalEntry
from app.models.user import User
from app.models.company import Company
from app.models.background_task import BackgroundTask


def test_ask_route_returns_task_id(monkeypatch, client_logged_in):
    client, _uid = client_logged_in
    monkeypatch.setattr(
        companion_routes.BackgroundTaskService, 'start_companion_ask',
        staticmethod(lambda user_id, question, history, focus: 'task-123'))

    resp = client.post('/companion/ask',
                       json={'question': 'hi', 'history': [], 'focus': {}})

    assert resp.status_code == 200
    assert resp.get_json()['data']['task_id'] == 'task-123'


def test_ask_status_returns_completed_result(client_logged_in):
    client, uid = client_logged_in
    db.session.add(BackgroundTask(
        id='t-done', user_id=uid, task_type='companion_ask', status='completed',
        result=json.dumps({'answer': 'the answer', 'hops': 1, 'tool_calls': []})))
    db.session.commit()

    resp = client.get('/companion/ask/status/t-done')
    assert resp.status_code == 200
    assert resp.get_json()['data']['result']['answer'] == 'the answer'


def test_ask_status_denies_foreign_task(client_logged_in):
    client, _uid = client_logged_in
    other = User(email='foreign@example.com')
    db.session.add(other)
    db.session.flush()
    db.session.add(BackgroundTask(
        id='t-foreign', user_id=other.id, task_type='companion_ask', status='completed'))
    db.session.commit()

    resp = client.get('/companion/ask/status/t-foreign')
    assert resp.status_code == 404


def test_ask_route_rejects_empty_question(client_logged_in):
    client, _uid = client_logged_in
    resp = client.post('/companion/ask', json={'question': '   ', 'focus': {}})
    assert resp.status_code == 400


def test_capture_route_creates_journal_entry(client_logged_in):
    client, uid = client_logged_in
    resp = client.post('/companion/capture',
                       json={'text': 'A captured insight.', 'source_title': 'Blog',
                             'url': 'https://example.com', 'focus': {}})

    assert resp.status_code == 200
    entry_id = resp.get_json()['data']['entry_id']
    entry = JournalEntry.query.get(entry_id)
    assert entry is not None and entry.user_id == uid


def test_capture_links_owned_company(client_logged_in):
    client, uid = client_logged_in
    company = Company(name='ASML Holding', ticker_symbol='ASML', user_id=uid)
    db.session.add(company)
    db.session.commit()

    resp = client.post('/companion/capture', json={
        'text': 'A note about ASML.',
        'focus': {'type': 'company', 'company_id': company.id}})

    assert resp.status_code == 200
    entry = JournalEntry.query.get(resp.get_json()['data']['entry_id'])
    assert entry.company_id == company.id


def test_capture_ignores_unowned_company(client_logged_in):
    client, uid = client_logged_in
    other = User(email='foreign@example.com')
    db.session.add(other)
    db.session.flush()
    foreign_company = Company(name='SAP SE', ticker_symbol='SAP', user_id=other.id)
    db.session.add(foreign_company)
    db.session.commit()

    resp = client.post('/companion/capture', json={
        'text': 'Trying to attach to a foreign company.',
        'focus': {'type': 'company', 'company_id': foreign_company.id}})

    # Capture still succeeds, but the unowned company id is rejected → linked to nothing.
    assert resp.status_code == 200
    entry = JournalEntry.query.get(resp.get_json()['data']['entry_id'])
    assert entry.company_id is None


def test_ask_requires_login(_app):
    # No session → login required → not a 200.
    resp = _app.test_client().post('/companion/ask', json={'question': 'hi'})
    assert resp.status_code != 200
