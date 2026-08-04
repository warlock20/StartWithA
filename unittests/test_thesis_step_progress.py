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

"""A thesis carried over from an idea isn't work the user has done yet.

Starting research from an idea seeds project.investment_thesis with the idea's
thesis_summary. Counting that as a finished thesis step made brand-new projects
report partial progress (a 2-step project opened at 50%).
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import db
from app.models import IdeaPipeline, ResearchProject, ResearchTemplate
from app.models.company import Company
from app.models.user import User
from app.services.step_progress_calculator import StepProgressCalculator

THESIS_STEP = {'type': 'thesis_writing', 'name': 'Investment Thesis'}
CHECKLIST_STEP = {'type': 'checklist', 'name': 'Checklist', 'config': {}}
SEEDED = 'A builder with a decent balance sheet.'


def _project(email, thesis=None, idea_thesis=None, steps=None):
    user = User(email=email)
    db.session.add(user)
    db.session.flush()
    uid = user.id

    company = Company(name='Bouvet ASA', ticker_symbol='BOUV', user_id=uid)
    db.session.add(company)
    db.session.flush()

    template = ResearchTemplate(user_id=uid, name='T', workflow_steps=[])
    db.session.add(template)
    db.session.flush()

    idea = None
    if idea_thesis is not None:
        idea = IdeaPipeline(user_id=uid, name='Bouvet', thesis_summary=idea_thesis)
        db.session.add(idea)
        db.session.flush()

    project = ResearchProject(
        user_id=uid, company_id=company.id, template_id=template.id,
        project_name='Deep Dive', investment_thesis=thesis,
        idea_id=idea.id if idea else None,
        workflow_snapshot=steps or [CHECKLIST_STEP, THESIS_STEP])
    db.session.add(project)
    db.session.commit()
    return project


def test_thesis_seeded_from_an_idea_is_not_progress(app_context):
    """The bug: a brand-new project from an idea opened at 50%."""
    project = _project('thesis-seeded@example.com', thesis=SEEDED, idea_thesis=SEEDED)

    assert StepProgressCalculator.get_step_progress(project, 1) == 0.0
    assert project.progress_percentage == 0.0


def test_editing_the_seeded_thesis_counts_as_progress(app_context):
    project = _project('thesis-edited@example.com',
                       thesis=SEEDED + ' Now with my own analysis.',
                       idea_thesis=SEEDED)

    assert StepProgressCalculator.get_step_progress(project, 1) == 100.0


def test_a_thesis_written_without_an_idea_counts_as_progress(app_context):
    project = _project('thesis-own@example.com', thesis='Entirely my own thinking.')

    assert StepProgressCalculator.get_step_progress(project, 1) == 100.0


def test_no_thesis_is_no_progress(app_context):
    project = _project('thesis-none@example.com')

    assert StepProgressCalculator.get_step_progress(project, 1) == 0.0


def test_completing_the_step_still_counts_even_if_unchanged(app_context):
    """Explicit completion always wins over the seeded-value check."""
    project = _project('thesis-completed@example.com', thesis=SEEDED, idea_thesis=SEEDED)
    project.completed_steps = [1]
    db.session.commit()

    assert StepProgressCalculator.get_step_progress(project, 1) == 100.0
