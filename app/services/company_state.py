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
One answer to "what state is this company in".

Four tables hold pieces of the answer -- Company, IdeaPipeline, ResearchProject
and MarketSweepDecision -- and they are a SEQUENCE, not competing opinions. An
idea's terminal value is 'promoted'; that is how it reached research, and it
stays true forever. If a kill happened, it happened one stage later. Every page
that reads only the idea therefore reports a company as alive that was rejected
months ago.

State is derived on every read and never stored. A stored column has to be kept
in sync by every write path and drifts the moment one forgets -- which is the
defect this module exists to fix, one layer up.
"""

from dataclasses import dataclass

from app import db
from app.models.company import Company
from app.models.idea_pipeline import IdeaPipeline
from app.models.market_sweep import MarketSweepDecision
from app.models.portfolio import PortfolioPosition
from app.models.research import ResearchProject


@dataclass(frozen=True)
class CompanyState:
    key: str                      # stable, for logic
    label: str                    # for display
    stage: str                    # sweep | pipeline | research | portfolio | none
    is_dead: bool                 # rejected at any stage
    reason: str | None            # why, when the deciding row recorded one
    source: tuple[str, int] | None  # ('research_project', 11) -- what decided it


@dataclass(frozen=True)
class CompanyFacts:
    """Everything the ladder needs for one company, already fetched."""
    company_id: int
    is_in_portfolio: bool
    project: dict | None
    ideas: list
    sweep_decision: dict | None
    has_closed_position: bool


_LABELS = {
    'held': ('Held', 'portfolio', False),
    'invest_decided': ('Invest decided', 'research', False),
    'killed_research': ('Killed in research', 'research', True),
    'watchlist': ('Watchlist', 'research', False),
    'researching': ('Researching', 'research', False),
    'promoted': ('Promoted', 'pipeline', False),
    'killed_pipeline': ('Killed in pipeline', 'pipeline', True),
    'someday': ('Someday', 'pipeline', False),
    'in_inbox': ('In inbox', 'pipeline', False),
    'killed_sweep': ('Killed at sweep', 'sweep', True),
    'skipped': ('Skipped at sweep', 'sweep', False),
    'exited': ('Exited', 'portfolio', False),
    'untracked': ('Untracked', 'none', False),
}


def _state(key, reason=None, source=None):
    label, stage, is_dead = _LABELS[key]
    return CompanyState(key=key, label=label, stage=stage, is_dead=is_dead,
                        reason=reason, source=source)


def resolve_state(facts):
    """Walk the ladder. First match wins."""
    project = facts.project
    src_p = ('research_project', project['id']) if project else None

    # 1. You own it. How you got there is history.
    if facts.is_in_portfolio:
        return _state('held', source=('company', facts.company_id))

    if project:
        # 2-5. Research has spoken, and it speaks after the idea stage.
        if project.get('decision') == 'invest':
            return _state('invest_decided', source=src_p)

        # 3. Three fields, because a kill is recorded differently depending on
        # which path wrote it. Catches rows written before the session_routes fix.
        if (project.get('status') == 'killed'
                or project.get('decision') == 'pass'
                or project.get('too_hard_reason')):
            reason = project.get('too_hard_reason') or project.get('kill_reason')
            return _state('killed_research', reason=reason, source=src_p)

        if project.get('decision') == 'watchlist':
            return _state('watchlist', source=src_p)

        if project.get('status') == 'active':
            return _state('researching', source=src_p)

    if facts.ideas:
        # 6. Any promoted idea beats any killed one: promotion means it was
        # never killed at that stage.
        for idea in facts.ideas:
            if idea.get('status') in ('promoted', 'survived'):
                return _state('promoted', source=('idea_pipeline', idea['id']))

        for idea in facts.ideas:
            if idea.get('status') == 'killed':
                return _state('killed_pipeline', reason=idea.get('kill_reason'),
                              source=('idea_pipeline', idea['id']))

        for idea in facts.ideas:
            if idea.get('status') == 'someday':
                return _state('someday', source=('idea_pipeline', idea['id']))

        for idea in facts.ideas:
            if idea.get('status') in ('inbox', 'killing'):
                return _state('in_inbox', source=('idea_pipeline', idea['id']))

    if facts.sweep_decision:
        decision = facts.sweep_decision.get('decision')
        src_s = ('market_sweep_decision', facts.sweep_decision['id'])
        if decision == 'killed':
            return _state('killed_sweep', source=src_s)
        if decision == 'skip':
            return _state('skipped', source=src_s)

    # 11. Held once, sold, and nothing active. Below every process rung so it
    # can never mask live work.
    if facts.has_closed_position:
        return _state('exited', source=('company', facts.company_id))

    return _state('untracked')


def company_states(user_id, company_ids=None):
    """State for many companies in a fixed five queries.

    Analytics evaluates every company a user owns -- 364 today. A per-company
    query would make that 1,821 round trips, so the facts are fetched in bulk
    and the ladder is walked in Python.
    """
    company_q = Company.query.filter(Company.user_id == user_id)
    if company_ids is not None:
        ids = list(company_ids)
        if not ids:
            return {}
        company_q = company_q.filter(Company.id.in_(ids))
    companies = company_q.all()
    if not companies:
        return {}

    ids = [c.id for c in companies]

    projects = {}
    for p in (ResearchProject.query
              .filter(ResearchProject.user_id == user_id,
                      ResearchProject.company_id.in_(ids)).all()):
        # uq_research_project_user_company guarantees at most one per company.
        projects[p.company_id] = {
            'id': p.id, 'status': p.status, 'decision': p.decision,
            'too_hard_reason': p.too_hard_reason, 'kill_reason': p.kill_reason,
        }

    ideas = {}
    for i in (IdeaPipeline.query
              .filter(IdeaPipeline.user_id == user_id,
                      IdeaPipeline.company_id.in_(ids))
              .order_by(IdeaPipeline.id).all()):
        ideas.setdefault(i.company_id, []).append(
            {'id': i.id, 'status': i.status, 'kill_reason': i.kill_reason})

    sweep = {}
    for decision, company_id in (
            db.session.query(MarketSweepDecision, IdeaPipeline.company_id)
            .join(IdeaPipeline, IdeaPipeline.id == MarketSweepDecision.promoted_idea_id)
            .filter(MarketSweepDecision.user_id == user_id,
                    IdeaPipeline.company_id.in_(ids)).all()):
        sweep.setdefault(company_id,
                         {'id': decision.id, 'decision': decision.decision})

    closed = {
        company_id for (company_id,) in
        db.session.query(PortfolioPosition.company_id)
        .filter(PortfolioPosition.user_id == user_id,
                PortfolioPosition.company_id.in_(ids),
                PortfolioPosition.is_active.is_(False)).all()
    }

    return {
        c.id: resolve_state(CompanyFacts(
            company_id=c.id,
            is_in_portfolio=bool(c.is_in_portfolio),
            project=projects.get(c.id),
            ideas=ideas.get(c.id, []),
            sweep_decision=sweep.get(c.id),
            has_closed_position=c.id in closed,
        ))
        for c in companies
    }


def company_state(user_id, company_id):
    """State for one company. An unknown company is 'untracked', not an error."""
    return company_states(user_id, [company_id]).get(
        company_id, _state('untracked'))
