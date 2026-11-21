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

"""Position coverage warnings: which open positions lack the plans they need."""

import math
from dataclasses import dataclass, field

from flask import url_for
from sqlalchemy.orm import joinedload

from app.models import Company, DestinationCheckpoint
from app.models.portfolio import PortfolioPosition
from app.services import findings
from app.services.config_service import ConfigKeys, get_config
from app.utils.time_utils import ensure_timezone_aware, now_utc, timedelta

DEFAULT_EXIT_PLAN_STALE_DAYS = 90
MAX_EXIT_PLAN_STALE_DAYS = 3650  # keep in step with max_value in the seeding migration


def exit_plan_stale_days() -> int:
    """Days without a rule review/update after which an exit plan is stale.

    Anything that is not a number in [1, MAX_EXIT_PLAN_STALE_DAYS] (including
    inf/nan) falls back to the default; decimals are truncated.
    """
    value = get_config(ConfigKeys.EXIT_PLAN_STALE_DAYS, default=DEFAULT_EXIT_PLAN_STALE_DAYS)
    try:
        days = float(value)
    except (TypeError, ValueError):
        return DEFAULT_EXIT_PLAN_STALE_DAYS
    if not math.isfinite(days) or not 1 <= days <= MAX_EXIT_PLAN_STALE_DAYS:
        return DEFAULT_EXIT_PLAN_STALE_DAYS
    return int(days)


def _rule_freshness(rule):
    """When the rule was last reviewed or edited, whichever is later.

    An edit after a review counts as attention too. A rule with neither date
    falls back to created_at, and to None (never fresh) when nothing is set.
    """
    dates = [d for d in (rule.last_reviewed, rule.updated_at) if d is not None]
    if not dates and rule.created_at is not None:
        dates = [rule.created_at]
    if not dates:
        return None
    return max(ensure_timezone_aware(d) for d in dates)


GAP_TYPES = ('no_exit_plan', 'no_active_checkpoint', 'checkpoints_all_past', 'exit_plan_stale')
GAP_SEVERITY = {
    'no_exit_plan': 'danger',
    'no_active_checkpoint': 'warning',
    'checkpoints_all_past': 'warning',
    'exit_plan_stale': 'info',
}
_SEVERITY_RANK = {'danger': 0, 'warning': 1, 'info': 2}


@dataclass
class Gap:
    type: str
    severity: str
    message: str
    fix_label: str
    fix_link: str


@dataclass
class PositionCoverage:
    position: PortfolioPosition
    company: Company
    has_exit_plan: bool
    has_active_checkpoint: bool
    has_future_checkpoint: bool
    exit_plan_stale: bool
    gaps: list = field(default_factory=list)

    @property
    def has_problems(self) -> bool:
        return bool(self.gaps)


class PositionCoverageService:
    """Which of a user's open positions lack an exit plan or a live checkpoint."""

    def __init__(self, user_id: int):
        self.user_id = user_id

    def positions(self) -> list:
        """One row per active position, problem rows (most severe gap first) then by name."""
        positions = (
            PortfolioPosition.query
            .options(joinedload(PortfolioPosition.company))
            .filter(PortfolioPosition.user_id == self.user_id,
                    PortfolioPosition.is_active.is_(True))
            .all()
        )
        if not positions:
            return []

        company_ids = {p.company_id for p in positions}
        checkpoints = {}
        for checkpoint in DestinationCheckpoint.query.filter(
                DestinationCheckpoint.user_id == self.user_id,
                DestinationCheckpoint.company_id.in_(company_ids),
                DestinationCheckpoint.status == 'Active'):
            checkpoints.setdefault(checkpoint.company_id, []).append(checkpoint)

        today = now_utc().date()
        stale_days = exit_plan_stale_days()
        cutoff = now_utc() - timedelta(days=stale_days)
        rules = findings.active_must_exits_by_company(self.user_id, company_ids)

        rows = [
            self._coverage(p, rules[p.company_id], checkpoints.get(p.company_id, []),
                           today, cutoff, stale_days)
            for p in positions
        ]
        rows.sort(key=lambda r: (
            not r.has_problems,
            min((_SEVERITY_RANK[g.severity] for g in r.gaps), default=0),
            (r.company.name or '').lower(),
        ))
        return rows

    @staticmethod
    def _coverage(position, rules, checkpoints, today, cutoff, stale_days) -> PositionCoverage:
        company = position.company
        has_exit_plan = bool(rules)
        has_active = bool(checkpoints)
        has_future = any(c.target_date >= today for c in checkpoints)
        fresh_dates = [_rule_freshness(rule) for rule in rules]
        stale = has_exit_plan and not any(d is not None and d >= cutoff for d in fresh_dates)

        plan_link = url_for('companies.company_detail', company_id=company.id,
                            _anchor='research/findings')
        checkpoint_link = url_for('companies.destination_analysis', company_id=company.id)
        gaps = []
        if not has_exit_plan:
            gaps.append(Gap('no_exit_plan', GAP_SEVERITY['no_exit_plan'], 'No exit plan',
                            'Add exit rule', plan_link))
        if not has_active:
            gaps.append(Gap('no_active_checkpoint', GAP_SEVERITY['no_active_checkpoint'],
                            'No active checkpoint', 'Add checkpoint', checkpoint_link))
        elif not has_future:
            gaps.append(Gap('checkpoints_all_past', GAP_SEVERITY['checkpoints_all_past'],
                            'All checkpoints are past', 'Add checkpoint', checkpoint_link))
        if stale:
            gaps.append(Gap('exit_plan_stale', GAP_SEVERITY['exit_plan_stale'],
                            f'Exit plan not reviewed in {stale_days} days',
                            'Review exit plan', plan_link))
        gaps.sort(key=lambda g: _SEVERITY_RANK[g.severity])
        return PositionCoverage(position, company, has_exit_plan, has_active, has_future,
                                stale, gaps)
