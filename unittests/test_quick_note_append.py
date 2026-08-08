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

"""Quick Add Note appends to a company's notes (#316)."""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import db
from app.models.company import Company
from app.models.user import User
from app.utils.blocknote_utils import append_note, blocknote_to_text


def _doc(*texts):
    """A BlockNote document of plain paragraphs, as the editor would send it."""
    return json.dumps([
        {'type': 'paragraph', 'props': {},
         'content': [{'type': 'text', 'text': t, 'styles': {}}]} for t in texts])


def test_append_note_to_empty_document():
    doc = append_note('', _doc('Freight costs up.'), '4 Aug 2026')
    blocks = json.loads(doc)

    assert blocks[0]['type'] == 'heading'
    assert blocks[0]['content'][0]['text'] == '4 Aug 2026'
    assert blocks[1]['content'][0]['text'] == 'Freight costs up.'


def test_append_note_keeps_the_editor_formatting():
    """Lists and styled runs must survive, not be flattened to plain text."""
    note = json.dumps([
        {'type': 'bulletListItem', 'props': {},
         'content': [{'type': 'text', 'text': 'Margin pressure',
                      'styles': {'bold': True}}]}])

    blocks = json.loads(append_note('', note, '4 Aug 2026'))

    assert blocks[1]['type'] == 'bulletListItem'
    assert blocks[1]['content'][0]['styles']['bold'] is True


def test_append_note_still_accepts_plain_text():
    blocks = json.loads(append_note('', 'just a string', '4 Aug 2026'))

    assert blocks[1]['content'][0]['text'] == 'just a string'


def test_append_note_keeps_existing_blocks():
    existing = json.dumps([
        {'type': 'paragraph', 'props': {},
         'content': [{'type': 'text', 'text': 'Earlier thought.', 'styles': {}}]}])

    doc = append_note(existing, _doc('Later thought.'), '4 Aug 2026')

    assert json.loads(doc)[0]['content'][0]['text'] == 'Earlier thought.'
    assert 'Later thought.' in doc


def test_append_note_keeps_plain_text_left_by_older_writes():
    """Never discard content just because it isn't BlockNote JSON."""
    doc = append_note('some legacy plain text', _doc('New note.'), '4 Aug 2026')

    text = blocknote_to_text(doc)
    assert 'some legacy plain text' in text
    assert 'New note.' in text


def test_append_note_keeps_json_that_is_not_a_list():
    doc = append_note('{"not": "a list"}', _doc('New note.'), '4 Aug 2026')

    assert 'New note.' in doc
    assert 'not' in doc


def test_endpoint_appends_and_stamps_the_timestamp(client_logged_in):
    client, uid = client_logged_in
    company = Company(name='ACME Corp', ticker_symbol='ACME', user_id=uid)
    db.session.add(company)
    db.session.commit()

    resp = client.post(f'/companies/api/{company.id}/journey-notes/append',
                       json={'content': _doc('Freight costs up 12% QoQ.'),
                             'project_name': 'Deep Dive'})

    assert resp.status_code == 200
    db.session.refresh(company)
    assert 'Freight costs up 12% QoQ.' in company.journey_notes
    assert 'Deep Dive' in company.journey_notes
    assert company.journey_notes_updated_at is not None


def test_endpoint_omits_the_dash_when_no_project_is_given(client_logged_in):
    client, uid = client_logged_in
    company = Company(name='ACME Corp', ticker_symbol='ACME', user_id=uid)
    db.session.add(company)
    db.session.commit()

    client.post(f'/companies/api/{company.id}/journey-notes/append',
                json={'content': _doc('From the company page.')})

    db.session.refresh(company)
    heading = json.loads(company.journey_notes)[0]['content'][0]['text']
    assert '—' not in heading


def test_endpoint_rejects_empty_text(client_logged_in):
    client, uid = client_logged_in
    company = Company(name='ACME Corp', ticker_symbol='ACME', user_id=uid)
    db.session.add(company)
    db.session.commit()

    resp = client.post(f'/companies/api/{company.id}/journey-notes/append',
                       json={'content': _doc('   ')})

    assert resp.status_code != 200 or not resp.get_json().get('success')
    db.session.refresh(company)
    assert not company.journey_notes


def test_endpoint_will_not_write_to_an_unowned_company(client_logged_in):
    client, _uid = client_logged_in
    other = User(email='foreign-note-append@example.com')
    db.session.add(other)
    db.session.flush()
    foreign = Company(name='SAP SE', ticker_symbol='SAP', user_id=other.id)
    db.session.add(foreign)
    db.session.commit()

    resp = client.post(f'/companies/api/{foreign.id}/journey-notes/append',
                       json={'content': _doc('Trying to write to a stranger.')})

    assert resp.status_code == 404
    db.session.refresh(foreign)
    assert not foreign.journey_notes
