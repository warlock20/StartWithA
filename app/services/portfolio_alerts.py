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
from app.services import findings
from app.services.checkpoint_analysis_service import CheckpointAnalysisService
from app.services.exit_watch import episodes as exit_episodes
from app.services.exit_watch import view as exit_view
from app.services.intelligence_engine import get_portfolio_warnings
from app.services.portfolio_intelligence import PortfolioIntelligenceService, get_learning_insights
from app.services.position_coverage import (
    GAP_SEVERITY, GAP_TYPES, PositionCoverageService, exit_plan_stale_days, rule_freshness)
from app.utils.time_utils import date

OVERDUE_LIMIT = 3
THIS_WEEK_LIMIT = 2
DIVERGING_LIMIT = 3

# Lane kind -> (pill label, rank); a lower rank is listed first.
LANE_KINDS = {
    'exit_triggered': ('Exit rule triggered', 0),
    'checkpoint_overdue': ('Checkpoint overdue', 1),
    'missing_plan': ('Missing plan', 2),
    'exit_at_risk': ('Exit rule at risk', 3),
    'checkpoint_at_risk': ('AI: at risk', 3),
    'needs_look': ('Needs a look', 4),
}
_AT_RISK_ASSESSMENTS = ('at_risk', 'likely_missed')
_LANE_DATE = '%d %b %Y'
_REVIEWED_DATE = '%d %b %Y'

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


@dataclass
class ItemAction:
    """One button on a lane row. kind: link, checkpoint_status, hold or still_valid."""
    label: str
    kind: str
    endpoint: str = ''
    values: dict = field(default_factory=dict)
    primary: bool = False
    rule_ids: list[int] = field(default_factory=list)
    checkpoint_id: Optional[int] = None
    status: Optional[str] = None
    reason_required: bool = True

    @property
    def link(self) -> str:
        """The target URL of a link action; needs a request context."""
        return url_for(self.endpoint, **self.values)

    @property
    def hold_url(self) -> str:
        return url_for('companies.api_hold_finding', company_id=self.values['company_id'],
                       entry_id=self.rule_ids[0])

    @property
    def review_urls(self) -> list:
        return [url_for('companies.api_review_finding', company_id=self.values['company_id'],
                        entry_id=rule_id) for rule_id in self.rule_ids]

    @property
    def status_url(self) -> str:
        return url_for('portfolio.update_checkpoint_status', checkpoint_id=self.checkpoint_id)


@dataclass
class ActionItem:
    """One thing the user has to act on, shown as a row in the Needs action list."""
    kind: str
    company_id: int
    ticker: str
    company_name: str
    title: str
    detail: str
    actions: list[ItemAction]
    gap_types: tuple[str, ...] = ()
    rule_id: Optional[int] = None
    checkpoint_id: Optional[int] = None
    target_date: Optional[date] = None  # overdue items sort by it

    @property
    def label(self) -> str:
        return LANE_KINDS[self.kind][0]

    @property
    def rank(self) -> int:
        return LANE_KINDS[self.kind][1]


def _checkpoint_title(cp) -> str:
    text = f'{cp.metric} {cp.expectation} by {cp.target_date.strftime(_LANE_DATE)}'
    return ' '.join(text.split())


def _assessment(insight) -> Optional[str]:
    """The AI status_assessment of a checkpoint insight, None without one."""
    return (insight.supporting_data or {}).get('status_assessment') if insight else None


def _status_words(assessment: str) -> str:
    return assessment.replace('_', ' ').lower()


def held_text(episode_info: dict) -> str:
    """"Held since <date>: <reason>", leaving out whichever parts are missing."""
    since = f' since {episode_info["held_display"]}' if episode_info.get('held_display') else ''
    reason = f': {episode_info["hold_reason"]}' if episode_info.get('hold_reason') else ''
    return f'Held{since}{reason}'


def source_text(source: dict) -> str:
    """"<title>, <published date>" of a check's source; the date is left out when unknown."""
    if not source.get('title'):
        return ''
    published = f', {source["published_display"]}' if source.get('published_display') else ''
    return f'{source["title"]}{published}'


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

    @cached_property
    def _alerting_exits(self) -> tuple:
        """(episodes, rules by id, companies by id) for the exit rules that need an answer."""
        episodes = exit_episodes.alerting(self.user_id)
        if not episodes:
            return [], {}, {}
        rules = {r.id: r for r in JournalEntry.query.filter(
            JournalEntry.id.in_([e.rule_id for e in episodes])).all()}
        companies = {c.id: c for c in Company.query.filter(
            Company.id.in_({e.company_id for e in episodes})).all()}
        return episodes, rules, companies

    @cached_property
    def rule_states(self) -> dict:
        """Exit-watch state of every rule in the coverage rows plus every alerting rule."""
        rule_ids = {rule.id for row in self.coverage for rule in row.rules}
        rule_ids.update(e.rule_id for e in self._alerting_exits[0])
        return exit_view.rule_states(self.user_id, rule_ids)

    @cached_property
    def checkpoint_insights(self) -> dict:
        ids = [cp.id for group in self.checkpoints_data.values() for cp in group]
        return CheckpointAnalysisService.get_checkpoint_insights(ids)

    def action_items(self) -> list:
        """The per-item list behind the Needs action lane, most urgent first.

        Needs a request context (the actions resolve URLs on read).
        """
        items = (self._exit_items() + self._overdue_items() + self._coverage_items()
                 + self._checkpoint_risk_items())
        items.sort(key=lambda i: (i.rank, i.target_date if i.kind == 'checkpoint_overdue' else date.min,
                                  i.company_name.lower(), i.title))
        return items

    def _exit_items(self) -> list:
        episodes, rules, companies = self._alerting_exits
        items = []
        for episode in episodes:
            rule, company = rules.get(episode.rule_id), companies.get(episode.company_id)
            if rule is None or company is None or episode.current_status not in ('triggered', 'at_risk'):
                continue
            state = self.rule_states.get(rule.id) or {}
            reask = episode.realert_reason == 'reask'
            if reask:
                info = state.get('episode') or {}
                detail = f'{held_text(info)}. Still holding?'
            else:
                source = next(iter(state.get('sources') or []), None)
                summary = state.get('display_summary') or ''
                if source and source.get('published_display'):
                    lead = source_text(source)
                elif state.get('checked_display'):
                    lead = f'Checked {state["checked_display"]}'
                else:
                    lead = ''
                detail = f'{lead}: {summary}' if lead and summary else (lead or summary)
            kind = 'exit_triggered' if episode.current_status == 'triggered' else 'exit_at_risk'
            hold = ItemAction('Still holding' if reask else 'Hold anyway', 'hold',
                              values={'company_id': company.id}, rule_ids=[rule.id],
                              reason_required=not reask)
            sell = ItemAction('Sell', 'link', 'portfolio.add_transaction',
                              {'company_id': company.id, 'type': 'SELL'}, primary=True)
            items.append(ActionItem(
                kind, company.id, company.ticker_symbol or '', company.name or '',
                findings.finding_text_from_editor(rule.content), detail, [sell, hold],
                rule_id=rule.id))
        return items

    def _overdue_items(self) -> list:
        items = []
        for cp in self.checkpoints_data.get('overdue', []):
            days = -cp.days_until
            detail = f'{days} day{"" if days == 1 else "s"} overdue.'
            insight = self.checkpoint_insights.get(cp.id)
            assessment = _assessment(insight)
            if assessment:
                detail += f' AI: {_status_words(assessment)}.'
            actions = [ItemAction('Met', 'checkpoint_status', checkpoint_id=cp.id, status='Met'),
                       ItemAction('Not met', 'checkpoint_status', checkpoint_id=cp.id, status='Not Met')]
            items.append(ActionItem('checkpoint_overdue', cp.company_id, cp.company_ticker,
                                    cp.company_name, _checkpoint_title(cp), detail, actions,
                                    checkpoint_id=cp.id, target_date=cp.target_date))
        return items

    def _coverage_items(self) -> list:
        items = []
        for row in self.coverage:
            company = row.company
            gaps = {g.type: g for g in row.gaps}
            identity = (company.id, company.ticker_symbol or '', company.name or '')
            missing = tuple(t for t in ('no_exit_plan', 'no_active_checkpoint') if t in gaps)
            if missing:
                if len(missing) == 2:
                    title, detail = ('No exit plan and no checkpoint',
                                     'Add at least one exit rule and one checkpoint.')
                elif missing[0] == 'no_exit_plan':
                    title, detail = 'No exit plan', 'Add at least one exit rule.'
                else:
                    title, detail = 'No active checkpoint', 'Add at least one checkpoint.'
                actions = [ItemAction(gaps[t].fix_label, 'link', gaps[t].fix_endpoint,
                                      gaps[t].fix_values, primary=i == 0)
                           for i, t in enumerate(missing)]
                items.append(ActionItem('missing_plan', *identity, title, detail, actions,
                                        gap_types=missing))
            look = tuple(t for t in ('checkpoints_all_past', 'exit_plan_stale') if t in gaps)
            if look:
                actions, titles, details = [], [], []
                if 'checkpoints_all_past' in gaps:
                    gap = gaps['checkpoints_all_past']
                    actions.append(ItemAction(gap.fix_label, 'link', gap.fix_endpoint, gap.fix_values))
                    titles.append('Only past checkpoints')
                    details.append('Add the next checkpoint')
                if 'exit_plan_stale' in gaps:
                    dates = [d for d in (rule_freshness(r) for r in row.rules) if d is not None]
                    reviewed = f'last reviewed {max(dates).strftime(_REVIEWED_DATE)}' if dates else 'never reviewed'
                    titles.append(f'Exit plan {reviewed}' if len(titles) == 0
                                  else f'the exit plan was {reviewed}')
                    details.append('confirm the exit rule still stands')
                    actions.append(ItemAction('Still valid', 'still_valid', values={'company_id': company.id},
                                              rule_ids=[r.id for r in row.rules], reason_required=False))
                title = ', and '.join(titles)
                detail = ', and '.join(details)
                detail = f'{detail[0].upper()}{detail[1:]}.'
                items.append(ActionItem('needs_look', *identity, title, detail, actions, gap_types=look))
        return items

    def _checkpoint_risk_items(self) -> list:
        items = []
        for group, cps in self.checkpoints_data.items():
            if group == 'overdue':
                continue
            for cp in cps:
                insight = self.checkpoint_insights.get(cp.id)
                assessment = _assessment(insight)
                if assessment not in _AT_RISK_ASSESSMENTS:
                    continue
                detail = f'AI: {_status_words(assessment)}.'
                if insight.title:
                    detail += f' {insight.title}'
                action = ItemAction('Review', 'link', 'companies.destination_analysis',
                                    {'company_id': cp.company_id}, primary=True)
                items.append(ActionItem('checkpoint_at_risk', cp.company_id, cp.company_ticker,
                                        cp.company_name, _checkpoint_title(cp), detail, [action],
                                        checkpoint_id=cp.id, target_date=cp.target_date))
        return items

    def _exit_rule_alerts(self) -> list:
        """Alerts for must-exit rules whose open trigger needs an answer, grouped by status."""
        episodes, rules, companies = self._alerting_exits
        if not episodes:
            return []
        tickers = {cid: c.ticker_symbol for cid, c in companies.items()}
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
