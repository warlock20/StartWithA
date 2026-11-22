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
from app.utils.time_utils import datetime, days_between, ensure_timezone_aware, naive_utc, now_utc, timedelta

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


ALERT_STATUSES = ('triggered', 'at_risk')
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
    fix_endpoint: str
    fix_values: dict = field(default_factory=dict)

    @property
    def fix_link(self) -> str:
        """The fix URL, resolved on read, so it needs a request context."""
        return url_for(self.fix_endpoint, **self.fix_values)


@dataclass
class PositionCoverage:
    position: PortfolioPosition
    company: Company
    has_exit_plan: bool
    has_active_checkpoint: bool
    has_future_checkpoint: bool
    exit_plan_stale: bool
    gaps: list = field(default_factory=list)
    rules: list = field(default_factory=list)

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

        plan_target = ('companies.company_detail',
                       {'company_id': company.id, '_anchor': 'research/findings'})
        checkpoint_target = ('companies.destination_analysis', {'company_id': company.id})
        gaps = []
        if not has_exit_plan:
            gaps.append(Gap('no_exit_plan', GAP_SEVERITY['no_exit_plan'], 'No exit plan',
                            'Add exit rule', *plan_target))
        if not has_active:
            gaps.append(Gap('no_active_checkpoint', GAP_SEVERITY['no_active_checkpoint'],
                            'No active checkpoint', 'Add checkpoint', *checkpoint_target))
        elif not has_future:
            gaps.append(Gap('checkpoints_all_past', GAP_SEVERITY['checkpoints_all_past'],
                            'All checkpoints are past', 'Add checkpoint', *checkpoint_target))
        if stale:
            gaps.append(Gap('exit_plan_stale', GAP_SEVERITY['exit_plan_stale'],
                            f'Exit plan not reviewed in {stale_days} days',
                            'Review exit plan', *plan_target))
        gaps.sort(key=lambda g: _SEVERITY_RANK[g.severity])
        return PositionCoverage(position, company, has_exit_plan, has_active, has_future,
                                stale, gaps, list(rules))


def _rule_dict(rule, state, now) -> dict:
    """One exit rule for the hub table: its entry plus the latest watch state (None when never checked)."""
    state = state or {}
    episode = state.get('episode') or {}
    ignored = episode.get('response') == 'ignored'
    ignored_days = None
    if ignored and episode.get('opened_at'):
        ignored_days = days_between(naive_utc(datetime.fromisoformat(episode['opened_at'])), now)
    return {
        'id': rule.id,
        'signal': rule.title,
        'text': findings.finding_text_from_editor(rule.content),
        'status': state.get('status'),
        'status_label': state.get('status_label'),
        'checked_at_display': state.get('checked_display'),
        'evidence_display': state.get('evidence_display'),
        'summary': state.get('display_summary'),
        'no_evidence': state.get('no_evidence', False),
        'sources': [{'url': s['url'], 'title': s['title'], 'published_display': s['published_display'],
                     'date_source': s.get('date_source')}
                    for s in state.get('sources', [])],
        'expired': state.get('expired', False),
        'held_since_display': episode.get('held_display') if episode.get('response') == 'held' else None,
        'hold_reason': episode.get('hold_reason'),
        'ignored': ignored,
        'ignored_days': ignored_days,
        'alerting': bool(episode.get('alerting')) and state.get('status') in ALERT_STATUSES,
        'findings_url': url_for('companies.company_detail', company_id=rule.company_id,
                                _anchor='research/findings'),
    }


def coverage_rows(coverage, rule_states=None) -> list:
    """JSON-ready dicts for the hub's coverage table, in the order given.

    rule_states is view.rule_states for the rules involved; a triggered or at-risk rule
    that is alerting makes its row a problem. Resolves URLs, so it needs a request context.
    """
    rule_states = rule_states or {}
    now = naive_utc(now_utc())
    out = []
    for row in coverage:
        rules = [_rule_dict(rule, rule_states.get(rule.id), now) for rule in row.rules]
        rule_problem = any(r['alerting'] for r in rules)
        out.append({
            'company_name': row.company.name,
            'ticker': row.company.ticker_symbol or '',
            'company_url': url_for('companies.company_detail', company_id=row.company.id),
            'has_exit_plan': row.has_exit_plan,
            'has_active_checkpoint': row.has_active_checkpoint,
            'has_future_checkpoint': row.has_future_checkpoint,
            'exit_plan_stale': row.exit_plan_stale,
            'has_problems': row.has_problems or rule_problem,
            'rule_problem': rule_problem,
            'rules': rules,
            'gaps': [
                {'type': g.type, 'message': g.message, 'fix_label': g.fix_label,
                 'fix_link': g.fix_link}
                for g in row.gaps
            ],
        })
    return out
