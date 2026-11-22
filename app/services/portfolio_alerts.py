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

"""One source of portfolio alerts, shared by the intelligence hub and the dashboard."""

from dataclasses import dataclass, field
from functools import cached_property
from typing import Optional

from flask import url_for

from app.constants import DEFAULT_CHECKPOINT_LOOKBACK_DAYS, MIN_TRADES_FOR_INSIGHTS
from app.models import Company, JournalEntry, ResearchOutcome
from app.services.exit_watch import episodes as exit_episodes
from app.services.intelligence_engine import get_portfolio_warnings
from app.services.portfolio_intelligence import PortfolioIntelligenceService, get_learning_insights
from app.services.position_coverage import GAP_SEVERITY, GAP_TYPES, PositionCoverageService, exit_plan_stale_days

OVERDUE_LIMIT = 3
THIS_WEEK_LIMIT = 2
DIVERGING_LIMIT = 3

_SEVERITY_RANK = {'danger': 0, 'warning': 1, 'info': 2}
_COVERAGE_ICONS = {
    'no_exit_plan': 'shield-exclamation',
    'no_active_checkpoint': 'calendar-x',
    'checkpoints_all_past': 'calendar2-x',
    'exit_plan_stale': 'hourglass-split',
}


@dataclass
class Alert:
    type: str
    severity: str
    icon: str
    message: str
    action: str
    link_endpoint: str
    link_values: dict = field(default_factory=dict)
    company_id: Optional[int] = None

    @property
    def link(self) -> str:
        """The alert URL, resolved on read, so it needs a request context."""
        return url_for(self.link_endpoint, **self.link_values)


def _coverage_message(gap_type: str, count: int) -> str:
    plural = count != 1
    if gap_type == 'no_exit_plan':
        return f'{count} positions have no exit plan' if plural else f'{count} position has no exit plan'
    if gap_type == 'no_active_checkpoint':
        return (f'{count} positions have no active checkpoint' if plural
                else f'{count} position has no active checkpoint')
    if gap_type == 'checkpoints_all_past':
        return (f'{count} positions have only past checkpoints' if plural
                else f'{count} position has only past checkpoints')
    if gap_type == 'exit_plan_stale':
        days = exit_plan_stale_days()
        return (f'{count} exit plans not reviewed in {days} days' if plural
                else f'{count} exit plan not reviewed in {days} days')
    raise ValueError(f'Unknown gap type: {gap_type}')


class PortfolioAlertsService:
    """Builds the ranked alert list for a user's portfolio."""

    def __init__(self, user_id: int):
        self.user_id = user_id

    @cached_property
    def checkpoints_data(self) -> dict:
        return PortfolioIntelligenceService(self.user_id).get_upcoming_checkpoints(
            days_ahead=DEFAULT_CHECKPOINT_LOOKBACK_DAYS)

    @cached_property
    def thesis_positions(self) -> list:
        return PortfolioIntelligenceService(self.user_id).get_thesis_reality_check()

    @cached_property
    def coverage(self) -> list:
        return PositionCoverageService(self.user_id).positions()

    def coverage_counts(self) -> dict:
        counts = {gap_type: 0 for gap_type in GAP_TYPES}
        for row in self.coverage:
            for gap in row.gaps:
                counts[gap.type] += 1
        return counts

    def strip_alerts(self) -> list:
        alerts = []

        counts = self.coverage_counts()
        for gap_type in GAP_TYPES:
            if counts[gap_type]:
                alerts.append(Alert(gap_type, GAP_SEVERITY[gap_type], _COVERAGE_ICONS[gap_type],
                                    _coverage_message(gap_type, counts[gap_type]), 'Fix',
                                    'portfolio.intelligence_hub', {'_anchor': 'coverage'}))

        for cp in self.checkpoints_data.get('overdue', [])[:OVERDUE_LIMIT]:
            alerts.append(Alert('checkpoint_overdue', 'danger', 'exclamation-triangle-fill',
                                f'{cp.company_ticker}: {cp.metric} is overdue', 'Review',
                                'portfolio.checkpoint_reminders', {}, cp.company_id))

        diverging = [p for p in self.thesis_positions if p.status == 'needs_attention']
        for pos in diverging[:DIVERGING_LIMIT]:
            alerts.append(Alert('thesis_diverging', 'warning', 'exclamation-circle',
                                f'{pos.company_ticker} thesis diverging ({pos.actual_return_pct:+.1f}%)',
                                'Check', 'portfolio.thesis_reality', {}, pos.company_id))

        for cp in self.checkpoints_data.get('this_week', [])[:THIS_WEEK_LIMIT]:
            alerts.append(Alert('checkpoint_this_week', 'info', 'calendar-event',
                                f'{cp.company_ticker}: {cp.metric} due this week', 'View',
                                'portfolio.checkpoint_reminders', {}, cp.company_id))

        alerts.extend(self._exit_rule_alerts())
        alerts.extend(self._insight_alerts())
        alerts.extend(self._warning_alerts())

        alerts.sort(key=lambda a: _SEVERITY_RANK[a.severity])  # stable within a severity
        return alerts

    def _exit_rule_alerts(self) -> list:
        """Alerts for must-exit rules whose open trigger needs an answer, grouped by status."""
        episodes = exit_episodes.alerting(self.user_id)
        if not episodes:
            return []
        rules = {r.id: r for r in JournalEntry.query.filter(
            JournalEntry.id.in_([e.rule_id for e in episodes])).all()}
        tickers = {c.id: c.ticker_symbol for c in Company.query.filter(
            Company.id.in_({e.company_id for e in episodes})).all()}
        alerts = []
        for status, word, severity, icon in (('triggered', 'triggered', 'danger', 'box-arrow-right'),
                                             ('at_risk', 'at risk', 'warning', 'exclamation-diamond')):
            group = [e for e in episodes if e.current_status == status and e.rule_id in rules]
            if len(group) == 1:
                episode = group[0]
                ticker, signal = tickers.get(episode.company_id), rules[episode.rule_id].title
                if episode.realert_reason == 'reask':
                    message = f'{ticker}: still holding through "{signal}"?'
                else:
                    message = f'{ticker}: exit rule "{signal}" {word}'
                alerts.append(Alert(f'exit_rule_{status}', severity, icon, message, 'Decide',
                                    'companies.company_detail',
                                    {'company_id': episode.company_id, '_anchor': 'research/findings'},
                                    episode.company_id))
            elif group:
                alerts.append(Alert(f'exit_rule_{status}', severity, icon,
                                    f'{len(group)} exit rules {word}', 'Decide',
                                    'portfolio.intelligence_hub', {'_anchor': 'coverage'}))
        return alerts

    def _insight_alerts(self) -> list:
        outcome_count = ResearchOutcome.query.filter(
            ResearchOutcome.user_id == self.user_id,
            ResearchOutcome.realized_return_pct.isnot(None),
        ).count()
        if outcome_count < MIN_TRADES_FOR_INSIGHTS:
            return []
        high = [i for i in get_learning_insights(self.user_id) if i.importance == 'high']
        if not high:
            return []
        return [Alert('learning_insight', 'info', 'lightbulb-fill',
                      f'New insight: "{high[0].title}"', 'View',
                      'portfolio.learning_insights')]

    def _warning_alerts(self) -> list:
        alerts = []
        for warning in get_portfolio_warnings(self.user_id):
            if warning.severity not in ('high', 'medium'):
                continue
            alerts.append(Alert('portfolio_warning',
                                'danger' if warning.severity == 'high' else 'warning',
                                'shield-exclamation',
                                f'{warning.title}: {warning.message[:50]}...', 'Review',
                                'portfolio.dashboard'))
        return alerts
