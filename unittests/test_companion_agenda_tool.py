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

"""
``get_agenda`` — the due/stalled/unanswered question shape (#317).

Regression cover for "Which of my holdings have checkpoints or thesis reviews
due?": the agent had no way to filter by ``target_date``/``status`` and burned
every hop on semantic search. These tests pin that the agenda answers by filter,
stays inside the horizon, and never shows another user's records.
"""

import os
import sys
import json
from datetime import timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest

from app import db
from app.models import Checklist, ChecklistItem
from app.models.checklist import DestinationCheckpoint
from app.models.idea_pipeline import (
    IdeaPipeline, KillAnswer, KillChecklist, KillCriterion, KillSession)
from app.models.portfolio import PortfolioPosition
from app.models.research import ChecklistAnalysis, ChecklistAnswer
from app.services.ai.tool_calling import ToolCall
from app.services.argos.agenda import STALLED_AFTER_DAYS
from app.services.argos.tools import ToolExecutor
from app.utils.time_utils import now_utc
from conftest import _make_company, _make_project, _make_user


def _checkpoint(user_id, company_id, days_from_today, status='Active', metric='EPS'):
    cp = DestinationCheckpoint(
        user_id=user_id, company_id=company_id, metric=metric,
        expectation='Beat estimates', status=status,
        target_date=now_utc().date() + timedelta(days=days_from_today))
    db.session.add(cp)
    db.session.flush()
    return cp


def _agenda(user_id, **args):
    result = ToolExecutor(user_id=user_id)(
        ToolCall(id='1', name='get_agenda', arguments=args))
    return json.loads(result.content)


@pytest.fixture
def user_with_holding(app_context):
    user = _make_user()
    company = _make_company(user.id, name='Copart, Inc.', ticker='CPRT')
    db.session.add(PortfolioPosition(
        user_id=user.id, company_id=company.id, is_active=True,
        total_shares=10, current_value=5000))
    db.session.commit()
    return user.id, company.id


# --- checkpoints ------------------------------------------------------------

def test_overdue_and_due_checkpoints_are_listed(app_context, user_with_holding):
    uid, cid = user_with_holding
    overdue = _checkpoint(uid, cid, -40, metric='Q2 revenue')
    soon = _checkpoint(uid, cid, 10, metric='Margin')
    db.session.commit()

    section = _agenda(uid)['checkpoints']
    ids = [i['checkpoint_id'] for i in section['items']]

    assert ids == [overdue.id, soon.id]           # ordered by date
    first = section['items'][0]
    assert first['overdue'] is True
    assert first['held'] is True
    assert first['company'] == 'Copart, Inc. (CPRT)'
    assert isinstance(first['citation'], int)


def test_checkpoints_respect_horizon_and_status(app_context, user_with_holding):
    uid, cid = user_with_holding
    _checkpoint(uid, cid, 60)                      # beyond a 30-day horizon
    _checkpoint(uid, cid, -5, status='Met')        # already resolved
    inside = _checkpoint(uid, cid, 20)
    db.session.commit()

    assert [i['checkpoint_id'] for i in _agenda(uid)['checkpoints']['items']] == [inside.id]
    # A wider horizon brings the far one in.
    assert _agenda(uid, horizon_days=90)['checkpoints']['total'] == 2


def test_bad_horizon_falls_back_to_default(app_context, user_with_holding):
    uid, _cid = user_with_holding
    assert _agenda(uid, horizon_days='soon')['horizon_days'] == 30
    assert _agenda(uid, horizon_days=10_000)['horizon_days'] == 365
    assert _agenda(uid, horizon_days=-3)['horizon_days'] == 1


def test_another_users_checkpoints_never_appear(app_context, user_with_holding):
    uid, _cid = user_with_holding
    other = _make_user(email='other@example.com')
    other_company = _make_company(other.id, name='Rival', ticker='RVL')
    _checkpoint(other.id, other_company.id, -1)
    db.session.commit()

    assert _agenda(uid)['checkpoints']['total'] == 0


# --- stalled projects -------------------------------------------------------

def test_idle_active_project_is_stalled(app_context, user_with_holding):
    uid, cid = user_with_holding
    project = _make_project(uid, cid)
    project.last_worked_at = now_utc() - timedelta(days=STALLED_AFTER_DAYS + 5)
    db.session.commit()

    items = _agenda(uid)['stalled_projects']['items']
    assert [i['project_id'] for i in items] == [project.id]
    assert items[0]['days_idle'] >= STALLED_AFTER_DAYS + 5


def test_recently_worked_project_is_not_stalled(app_context, user_with_holding):
    uid, cid = user_with_holding
    project = _make_project(uid, cid)
    project.last_worked_at = now_utc() - timedelta(days=1)
    db.session.commit()

    assert _agenda(uid)['stalled_projects']['total'] == 0


# --- checklist runs and kill sessions ---------------------------------------

def test_in_progress_checklist_with_unanswered_questions(app_context, user_with_holding):
    uid, cid = user_with_holding
    checklist = Checklist(name='Quality', user_id=uid)
    db.session.add(checklist)
    db.session.flush()
    items = [ChecklistItem(text=q, checklist_id=checklist.id, order=n)
             for n, q in enumerate(('Moat?', 'Management?', 'Valuation?'))]
    db.session.add_all(items)
    db.session.flush()
    run = ChecklistAnalysis(user_id=uid, company_id=cid, checklist_id=checklist.id)
    db.session.add(run)
    db.session.flush()
    db.session.add(ChecklistAnswer(
        checklist_analysis_id=run.id, checklist_item_id=items[0].id, answer_text='Yes'))
    # Blank answers don't count as answered.
    db.session.add(ChecklistAnswer(
        checklist_analysis_id=run.id, checklist_item_id=items[1].id, answer_text='  '))
    db.session.commit()

    entry = _agenda(uid)['open_checklist_runs']['items'][0]
    assert entry['analysis_id'] == run.id
    assert entry['total_items'] == 3
    assert entry['unanswered_items'] == 2


def test_open_kill_session_with_unanswered_criteria(app_context, user_with_holding):
    uid, _cid = user_with_holding
    kill_list = KillChecklist(user_id=uid, name='Kill fast')
    idea = IdeaPipeline(user_id=uid, name='Some idea')
    db.session.add_all([kill_list, idea])
    db.session.flush()
    criteria = [KillCriterion(kill_checklist_id=kill_list.id, question=q, order=n)
                for n, q in enumerate(('Debt?', 'Fraud?'))]
    db.session.add_all(criteria)
    db.session.flush()
    session = KillSession(user_id=uid, idea_id=idea.id, kill_checklist_id=kill_list.id)
    db.session.add(session)
    db.session.flush()
    db.session.add(KillAnswer(
        kill_session_id=session.id, criterion_id=criteria[0].id, passed=True))
    db.session.commit()

    entry = _agenda(uid)['open_kill_sessions']['items'][0]
    assert entry['idea'] == 'Some idea'
    assert entry['total_criteria'] == 2
    assert entry['unanswered_criteria'] == 1


# --- thesis drift -----------------------------------------------------------

def test_losing_position_shows_as_thesis_drift(app_context):
    user = _make_user()
    company = _make_company(user.id)
    db.session.add(PortfolioPosition(
        user_id=user.id, company_id=company.id, is_active=True,
        total_shares=10, current_value=5000, unrealized_gain_loss_pct=-30,
        first_purchase_date=now_utc().date() - timedelta(days=400)))
    db.session.commit()

    items = _agenda(user.id)['thesis_drift']['items']
    assert [i['company_id'] for i in items] == [company.id]
    assert items[0]['status'] == 'needs_attention'


def test_empty_account_returns_empty_sections(app_context):
    user = _make_user()
    db.session.commit()
    agenda = _agenda(user.id)
    for key in ('checkpoints', 'stalled_projects', 'open_checklist_runs',
                'open_kill_sessions', 'thesis_drift'):
        assert agenda[key] == {'total': 0, 'items': []}
