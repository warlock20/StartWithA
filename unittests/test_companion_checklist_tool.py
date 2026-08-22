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
The checklist-run page: focus declaration + the tool that reads it.

Regression cover for the id-collision bug. On
``/research/workflow/checklist/17/item/12`` the page declared no focus, so the
agent saw only the URL, guessed that ``17`` was a ``project_id``, and called
``get_research_project(17)`` — which resolved to a DIFFERENT company's project
that the user also owned, so no error was ever raised and the wrong company was
reported back as fact.

Two things have to hold for that not to recur: the page states its ids
explicitly, and the checklist run is readable through a tool of its own.
"""

import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest

from app import db
from app.models import Checklist, ChecklistItem
from app.models.research import ChecklistAnalysis, ChecklistAnswer
from app.services.ai.tool_calling import ToolCall
from app.services.argos.agent import _render_focus
from app.services.argos.tools import COMPANION_TOOLS, ToolExecutor
from conftest import _make_company, _make_user

ROOT = os.path.join(os.path.dirname(__file__), '..')
RESEARCH_STEP = os.path.join(
    ROOT, 'app/research_workflow/templates/research_step.html')


def _make_checklist_run(user_id, company_id, name="Kiran's Checklist",
                        questions=('Moat?', 'Management?', 'Valuation?'),
                        answered=1):
    """A checklist + items + an in-progress analysis. Returns (analysis, items)."""
    checklist = Checklist(name=name, user_id=user_id)
    db.session.add(checklist)
    db.session.flush()

    items = []
    for order, text in enumerate(questions):
        item = ChecklistItem(text=text, checklist_id=checklist.id, order=order)
        db.session.add(item)
        items.append(item)
    db.session.flush()

    analysis = ChecklistAnalysis(
        user_id=user_id, company_id=company_id, checklist_id=checklist.id)
    db.session.add(analysis)
    db.session.flush()

    for item in items[:answered]:
        db.session.add(ChecklistAnswer(
            checklist_analysis_id=analysis.id, checklist_item_id=item.id,
            answer_text='Prior answer.', satisfaction_status='satisfied'))
    db.session.commit()
    return analysis, items


@pytest.fixture
def seed_checklist_run(app_context):
    """A user mid-run on a checklist. Returns (uid, analysis, items)."""
    user = _make_user()
    company = _make_company(user.id, name='Copart, Inc.', ticker='CPRT')
    db.session.commit()
    analysis, items = _make_checklist_run(user.id, company.id)
    return user.id, analysis, items


# --- the tool ---------------------------------------------------------------

def test_registry_exposes_the_checklist_tool():
    """Without this the page's core question is simply unanswerable."""
    assert 'get_checklist_progress' in {t.name for t in COMPANION_TOOLS}


def test_tool_names_the_question_the_user_is_on(app_context, seed_checklist_run):
    uid, analysis, items = seed_checklist_run
    result = ToolExecutor(user_id=uid)(ToolCall(
        id='1', name='get_checklist_progress',
        arguments={'analysis_id': analysis.id, 'item_id': items[1].id}))
    payload = json.loads(result.content)

    assert payload['company'] == 'Copart, Inc.'
    assert payload['current_item']['question'] == 'Management?'
    assert payload['current_item']['number'] == 2       # position, not the raw id
    assert payload['total_items'] == 3
    assert payload['answered_items'] == 1


def test_tool_works_without_an_item(app_context, seed_checklist_run):
    """Progress alone is a valid question ('how far through am I?')."""
    uid, analysis, _items = seed_checklist_run
    result = ToolExecutor(user_id=uid)(ToolCall(
        id='1', name='get_checklist_progress',
        arguments={'analysis_id': analysis.id}))
    payload = json.loads(result.content)

    assert payload['current_item'] is None
    assert payload['answered_items'] == 1


def test_tool_denies_another_users_analysis(app_context, seed_checklist_run):
    """The bug's real sting: a plausible id must not silently return data."""
    _uid, analysis, _items = seed_checklist_run
    other = _make_user(email='other@example.com')
    db.session.commit()

    result = ToolExecutor(user_id=other.id)(ToolCall(
        id='1', name='get_checklist_progress',
        arguments={'analysis_id': analysis.id}))
    assert 'error' in json.loads(result.content)


def test_tool_rejects_an_item_from_another_checklist(app_context, seed_checklist_run):
    """A mismatched pair is a wrong question, not a different one — refuse it."""
    uid, analysis, _items = seed_checklist_run
    company = _make_company(uid, name='Gévelot SA', ticker='ALGEV')
    db.session.commit()
    _other_analysis, other_items = _make_checklist_run(
        uid, company.id, name='Other', questions=('Unrelated?',))

    result = ToolExecutor(user_id=uid)(ToolCall(
        id='1', name='get_checklist_progress',
        arguments={'analysis_id': analysis.id, 'item_id': other_items[0].id}))
    payload = json.loads(result.content)

    assert payload['current_item'] is None
    assert 'item_error' in payload          # the run still reports; the item doesn't
    assert 'Unrelated?' not in result.content


# --- the focus the page declares -------------------------------------------

def test_render_focus_states_checklist_ids():
    rendered = _render_focus({
        'type': 'checklist', 'company_id': 123,
        'analysis_id': 17, 'item_id': 12,
        'path': '/research/workflow/checklist/17/item/12'})

    assert 'Checklist analysis id: 17' in rendered
    assert 'Checklist item id: 12' in rendered


def test_research_step_page_declares_its_focus():
    """The root cause: this template declared nothing, so the agent guessed."""
    html = open(RESEARCH_STEP, encoding='utf-8').read()

    assert 'companion_focus' in html
    assert "'checklist'" in html
    assert 'analysis_id' in html
    assert 'item_id' in html


def test_research_step_does_not_declare_a_project_id():
    """A ChecklistAnalysis has no FK to ResearchProject — claiming one re-invents
    exactly the mix-up this page caused. Checks the declaration, not the prose
    around it, which is free to explain why the key is absent."""
    html = open(RESEARCH_STEP, encoding='utf-8').read()
    start = html.index('companion_focus =')
    declaration = html[start:html.index('%}', start)]
    assert 'project_id' not in declaration
