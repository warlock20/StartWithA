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

"""The inbox must ship the whole thesis and notes to the browser.

The page used to truncate the thesis to 80 characters server-side, which made
the full text unreachable and silently broke search for terms past that cut.
"""

import json
import re

import pytest

from app import db
from app.models import IdeaPipeline, KillChecklist, KillCriterion, User

# Roughly 440 characters — comfortably past the old 80-character cut.
LONG_THESIS = (
    'The RBI embargo on new digital onboarding was lifted in February, but the '
    'market is still applying the discount it opened during the ban. '
) * 4

# json.dumps writes a single line, so a line-anchored match is exact.
IDEAS_DATA_RE = re.compile(r'^const ideasData = (.+);$', re.M)


def _extract_ideas(html):
    match = IDEAS_DATA_RE.search(html)
    assert match, 'ideasData was not rendered into the inbox page'
    return json.loads(match.group(1))


@pytest.fixture
def inbox_client(client_logged_in):
    """Logged-in client whose user already owns a kill checklist.

    Without one, `inbox()` creates a default and redirects to its edit page.
    Also gives the user a username: `client_logged_in`'s user has none, and
    the base template's topbar avatar (`current_user.username[:2]`) blows up
    on a full page render without it. Every other consumer of
    `client_logged_in` only hits JSON API routes, so this gap was latent.
    """
    client, user_id = client_logged_in
    db.session.get(User, user_id).username = 'tester'
    checklist = KillChecklist(user_id=user_id, name='Default', is_default=True)
    db.session.add(checklist)
    db.session.flush()
    db.session.add(KillCriterion(
        kill_checklist_id=checklist.id, question='Do I understand it?', order=0))
    db.session.commit()
    return client, user_id


def test_thesis_is_sent_untruncated(inbox_client):
    client, user_id = inbox_client
    db.session.add(IdeaPipeline(
        user_id=user_id, name='Kotak Mahindra Bank', status='inbox',
        thesis_summary=LONG_THESIS))
    db.session.commit()

    ideas = _extract_ideas(client.get('/ideas/inbox').get_data(as_text=True))

    assert len(ideas) == 1
    assert ideas[0]['thesis'] == LONG_THESIS
    assert '...' not in ideas[0]['thesis']


def test_initial_notes_are_serialised(inbox_client):
    client, user_id = inbox_client
    db.session.add(IdeaPipeline(
        user_id=user_id, name='Nvidia', status='inbox',
        thesis_summary='Inference demand is mispriced.',
        initial_notes='Cross-check TSMC CoWoS capacity before promoting.'))
    db.session.commit()

    ideas = _extract_ideas(client.get('/ideas/inbox').get_data(as_text=True))

    assert ideas[0]['notes'] == 'Cross-check TSMC CoWoS capacity before promoting.'


def test_absent_thesis_and_notes_become_empty_strings(inbox_client):
    client, user_id = inbox_client
    db.session.add(IdeaPipeline(
        user_id=user_id, name='Tata Motors', status='inbox'))
    db.session.commit()

    ideas = _extract_ideas(client.get('/ideas/inbox').get_data(as_text=True))

    assert ideas[0]['thesis'] == ''
    assert ideas[0]['notes'] == ''
