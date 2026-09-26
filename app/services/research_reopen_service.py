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

"""Pull a rejected company back into research, whichever stage rejected it.

A kill is recorded in a different table at each stage -- sweep, pipeline,
research -- so every page that wanted to undo one grew its own partial version.
`reactivate_project` handled research passes only, refused screening kills, and
wiped the reason; `/ideas/<id>/resurrect` handled pipeline kills and dropped
them back in the inbox. This is the one place that knows how to undo a kill,
and it always takes the snapshot first.
"""

from dataclasses import dataclass

from app import db
from app.models.company import Company
from app.models.idea_pipeline import IdeaPipeline
from app.models.market_sweep import MarketSweepDecision
from app.models.research import ResearchProject
from app.models.research_reopening import ResearchReopening
from app.services.company_state import company_state
from app.utils.time_utils import now_utc


class ReopenNotAllowed(Exception):
    """The company is not in a rejected state, so there is nothing to reopen."""


@dataclass(frozen=True)
class ReopenResult:
    target: str            # 'project' -> that project's dashboard; 'routing' -> template picker
    project_id: int | None
    reopening_id: int


class ResearchReopenService:

    @staticmethod
    def reopen(user_id, company_id, what_changed=None):
        company = Company.query.filter_by(id=company_id, user_id=user_id).first()
        if company is None:
            raise ReopenNotAllowed('Company not found')

        state = company_state(user_id, company_id)
        if not state.is_dead or not state.source:
            raise ReopenNotAllowed(f'{company.name} is not in the too-hard pile')

        table, row_id = state.source
        what_changed = (what_changed or '').strip() or None

        if table == 'research_project':
            return ResearchReopenService._reopen_project(
                user_id, company, row_id, what_changed)
        if table == 'idea_pipeline':
            return ResearchReopenService._reopen_idea(
                user_id, company, row_id, what_changed)
        if table == 'market_sweep_decision':
            return ResearchReopenService._reopen_sweep(
                user_id, company, row_id, what_changed)

        raise ReopenNotAllowed(f'Cannot reopen a kill recorded in {table}')

    @staticmethod
    def _reopen_project(user_id, company, project_id, what_changed):
        project = ResearchProject.query.filter_by(
            id=project_id, user_id=user_id).first()
        if project is None:
            raise ReopenNotAllowed('Research project not found')

        reopening = ResearchReopening(
            user_id=user_id, company_id=company.id, project_id=project.id,
            prior_stage='research',
            prior_reason=project.too_hard_reason or project.kill_reason,
            prior_notes=project.too_hard_notes or project.decision_notes,
            prior_killed_at=project.abandoned_at or project.decision_date,
            what_changed=what_changed,
        )
        db.session.add(reopening)

        # Every field the ladder reads as a kill has to go, or the project
        # reads as 'killed_research' the moment the page reloads.
        project.status = 'active'
        project.decision = None
        project.decision_date = None
        project.too_hard_reason = None
        project.too_hard_notes = None
        project.kill_reason = None
        project.abandoned_at = None
        project.last_worked_at = now_utc()

        db.session.commit()
        return ReopenResult(target='project', project_id=project.id,
                            reopening_id=reopening.id)

    @staticmethod
    def _reopen_idea(user_id, company, idea_id, what_changed):
        idea = IdeaPipeline.query.filter_by(id=idea_id, user_id=user_id).first()
        if idea is None:
            raise ReopenNotAllowed('Idea not found')

        reopening = ResearchReopening(
            user_id=user_id, company_id=company.id, idea_id=idea.id,
            prior_stage='pipeline', prior_reason=idea.kill_reason,
            prior_notes=idea.initial_notes, prior_killed_at=idea.killed_at,
            what_changed=what_changed,
        )
        db.session.add(reopening)

        # 'promoted' outranks 'killed' on the ladder, so kill_reason and
        # killed_at stay put as history -- nothing has to be erased here.
        idea.status = 'promoted'
        idea.promoted_at = now_utc()

        db.session.commit()
        return ReopenResult(target='routing', project_id=None,
                            reopening_id=reopening.id)

    @staticmethod
    def _reopen_sweep(user_id, company, decision_id, what_changed):
        decision = MarketSweepDecision.query.filter_by(
            id=decision_id, user_id=user_id).first()
        if decision is None:
            raise ReopenNotAllowed('Sweep decision not found')

        # Defensive, and in practice unreachable. sweep_decide() always writes
        # an IdeaPipeline row with status='killed' alongside the decision
        # (sweep_routes.py, the decision_type == 'killed' branch), so the
        # ladder resolves a real sweep kill to 'killed_pipeline' with an
        # idea_pipeline source -- reopen() takes the idea branch and never
        # reaches this method at all. Consequences: prior_stage will not hold
        # 'sweep' for any kill the app can currently produce (a sweep kill is
        # snapshotted as 'pipeline'), and neither this method nor the fallback
        # below is exercised by a test. Kept so a future write path that kills
        # a sweep row without an idea does not leave reopen() with an
        # unhandled branch. See test_a_real_sweep_kill_reopens_through_the_idea
        # in unittests/test_research_reopen_service.py for what really happens.
        if decision.promoted_idea_id:
            return ResearchReopenService._reopen_idea(
                user_id, company, decision.promoted_idea_id, what_changed)

        reasons = decision.kill_reasons
        if isinstance(reasons, list):
            prior_reason = '; '.join(
                (r.get('reason') or r.get('question') or str(r))
                if isinstance(r, dict) else str(r)
                for r in reasons) or None
        else:
            prior_reason = reasons

        # A sweep kill with no idea row leaves nothing the ladder can move off
        # 'killed_sweep', and routing would bounce the user straight back here.
        # Give the company the promoted idea that sweep_decide would have
        # written, which is also what links the decision to the pipeline.
        #
        # Unreachable twice over: the ladder never names a market_sweep_decision
        # as the source of a dead company (the killed idea outranks it), and
        # even if it did, the promoted_idea_id branch above would win. No test,
        # and none is expected until a write path exists that can reach it.
        idea = IdeaPipeline(
            user_id=user_id, company_id=company.id, name=company.name,
            ticker_symbol=company.ticker_symbol, idea_type='company',
            status='promoted', promoted_at=now_utc(),
            source='reopened from sweep',
        )
        db.session.add(idea)
        db.session.flush()
        decision.promoted_idea_id = idea.id
        decision.decision = 'inbox'

        reopening = ResearchReopening(
            user_id=user_id, company_id=company.id, idea_id=idea.id,
            prior_stage='sweep',
            prior_reason=prior_reason or None,
            prior_killed_at=decision.decided_at,
            what_changed=what_changed,
        )
        db.session.add(reopening)

        db.session.commit()
        return ReopenResult(target='routing', project_id=None,
                            reopening_id=reopening.id)
