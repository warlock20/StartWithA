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

"""The Checkpoints page: metrics, per-position cards, date buckets and sold companies."""

from dataclasses import dataclass, field
from functools import cached_property
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app import db
from app.models import DestinationCheckpoint, ThesisEvolution
from app.models.portfolio import PortfolioPosition, Transaction
from app.services import findings
from app.services.portfolio_alerts import PortfolioAlertsService, held_text, source_text
from app.services.position_coverage import exit_plan_stale_days, rule_freshness
from app.utils.time_utils import date, now_utc, timedelta

HEALTHY_COLLAPSE_THRESHOLD = 12
THESIS_MAX_CHARS = 160
DUE_SOON_DAYS = 30
_AT_RISK_ASSESSMENTS = ('at_risk', 'likely_missed')
_REVIEWED_DATE = '%d %b %Y'

# Badge order doubles as severity order: (key, label, tone)
_BADGES = (
    ('triggered', 'Exit rule triggered', 'danger'),
    ('overdue', 'Checkpoint overdue', 'danger'),
    ('no_exit_plan', 'No exit plan', 'danger'),
    ('no_active_checkpoint', 'No checkpoint', 'warning'),
    ('checkpoints_all_past', 'Only past checkpoints', 'warning'),
    ('exit_plan_stale', 'Exit plan not reviewed', 'info'),
    ('held', 'Held through trigger', 'held'),
)
_RANKS = {'triggered': 0, 'overdue': 1, 'no_exit_plan': 2, 'no_active_checkpoint': 2,
          'at_risk': 3, 'checkpoints_all_past': 4, 'exit_plan_stale': 4}
_STATE_LABELS = {'met': 'Met', 'not_met': 'Not met', 'overdue': 'Overdue',
                 'due_soon': 'Due soon', 'upcoming': 'Upcoming'}
_RULE_LABELS = {'triggered': 'Triggered', 'at_risk': 'At risk', 'held': 'Held through trigger',
                'intact': 'Intact', 'unchecked': 'Not checked yet'}


@dataclass
class Metric:
    key: str
    label: str
    value: str
    sub: str
    icon: str
    tone: str  # danger, warning, neutral or success


@dataclass
class CardCheckpoint:
    id: int
    target_date: date
    metric: str
    expectation: str
    state: str  # met, not_met, overdue, due_soon or upcoming
    state_label: str
    ai_status: Optional[str]
    ai_label: Optional[str]
    can_resolve: bool


@dataclass
class CardRule:
    id: int
    text: str
    status: str  # triggered, at_risk, held, stale, intact or unchecked
    label: str
    detail: str


@dataclass
class Badge:
    label: str
    tone: str  # danger, warning, info or held


@dataclass
class PositionCard:
    company_id: int
    ticker: str
    name: str
    shares: int
    held_label: str
    return_pct: Optional[float]
    thesis: Optional[str]
    badges: list[Badge]
    checkpoints: list[CardCheckpoint]
    rules: list[CardRule]
    rank: Optional[int]
    gaps: list = field(default_factory=list)

    @property
    def has_problems(self) -> bool:
        return self.rank is not None


@dataclass
class DateBucket:
    key: str
    label: str
    items: list  # CheckpointReminder


@dataclass
class NotHeld:
    company_id: int
    ticker: str
    name: str
    sold_on: Optional[date]
    met: int
    not_met: int
    active: int


def _plural(count: int, word: str) -> str:
    return f'{count} {word}' if count == 1 else f'{count} {word}s'


def _held_label(shares: int, days: int, imported: bool) -> str:
    unit = 'share' if shares == 1 else 'shares'
    if imported:
        return f'{shares} {unit} · imported'
    if days < 60:
        span = _plural(days, 'day')
    elif days < 730:
        span = _plural(min(days // 30, 23), 'month')
    else:
        span = _plural(days // 365, 'year')
    return f'{shares} {unit} · held {span}'


def _one_line(text: str) -> Optional[str]:
    text = ' '.join((text or '').split())
    if not text:
        return None
    return text if len(text) <= THESIS_MAX_CHARS else text[:THESIS_MAX_CHARS].rstrip() + '…'


def _checkpoint_state(cp, today) -> str:
    if cp.status == 'Met':
        return 'met'
    if cp.status == 'Not Met':
        return 'not_met'
    days = (cp.target_date - today).days
    if days < 0:
        return 'overdue'
    return 'due_soon' if days <= DUE_SOON_DAYS else 'upcoming'


def _alerting(state) -> bool:
    return bool(((state or {}).get('episode') or {}).get('alerting'))


class CheckpointsPageService:
    """Everything the Checkpoints page shows, built on one PortfolioAlertsService."""

    def __init__(self, user_id: int):
        self.user_id = user_id

    @cached_property
    def alerts(self) -> PortfolioAlertsService:
        return PortfolioAlertsService(self.user_id)

    @cached_property
    def _today(self) -> date:
        return now_utc().date()

    @cached_property
    def _stale_days(self) -> int:
        return exit_plan_stale_days()

    @cached_property
    def _stale_cutoff(self):
        return now_utc() - timedelta(days=self._stale_days)

    @cached_property
    def _held_ids(self) -> set:
        return {row.company.id for row in self.alerts.coverage}

    @cached_property
    def _checkpoints_by_company(self) -> dict:
        """Every checkpoint of the user, any status, by company id (one query)."""
        grouped = {}
        for cp in (DestinationCheckpoint.query
                   .options(joinedload(DestinationCheckpoint.company))
                   .filter(DestinationCheckpoint.user_id == self.user_id)
                   .order_by(DestinationCheckpoint.target_date.asc(), DestinationCheckpoint.id.asc())):
            grouped.setdefault(cp.company_id, []).append(cp)
        return grouped

    @cached_property
    def _theses(self) -> dict:
        """The current thesis text by held company id (one query)."""
        if not self._held_ids:
            return {}
        theses = {}
        for thesis in (ThesisEvolution.query
                       .filter(ThesisEvolution.user_id == self.user_id,
                               ThesisEvolution.company_id.in_(self._held_ids),
                               ThesisEvolution.is_current.is_(True))
                       .order_by(ThesisEvolution.version.asc())):
            theses[thesis.company_id] = thesis.thesis_text
        return theses

    @cached_property
    def _trades(self) -> dict:
        """company id -> (every BUY imported?, latest SELL date) for held and checkpointed companies."""
        company_ids = self._held_ids | set(self._checkpoints_by_company)
        if not company_ids:
            return {}
        is_buy, is_sell = Transaction.type == 'BUY', Transaction.type == 'SELL'
        rows = (db.session.query(
                    Transaction.company_id,
                    func.bool_and(Transaction.is_imported).filter(is_buy),
                    func.max(Transaction.date).filter(is_sell))
                .filter(Transaction.user_id == self.user_id, Transaction.company_id.in_(company_ids))
                .group_by(Transaction.company_id).all())
        return {company_id: (bool(imported), sold_on) for company_id, imported, sold_on in rows}

    @cached_property
    def _lane(self) -> list:
        return self.alerts.action_items()

    def lane(self) -> list:
        return self._lane

    # Rules

    def _card_rule(self, rule) -> CardRule:
        state = self.alerts.rule_states.get(rule.id)
        episode = (state or {}).get('episode') or {}
        text = findings.finding_text_from_editor(rule.content)
        status = (state or {}).get('status')
        if _alerting(state) and status in ('triggered', 'at_risk'):
            return CardRule(rule.id, text, status, _RULE_LABELS[status], self._check_detail(state))
        if episode.get('response') == 'held':
            return CardRule(rule.id, text, 'held', _RULE_LABELS['held'], held_text(episode))
        if status in ('triggered', 'at_risk'):
            detail = (f'Not checked since {state["checked_display"]}'
                      if state.get('expired') and state.get('checked_display')
                      else self._check_detail(state))
            return CardRule(rule.id, text, status, _RULE_LABELS[status], detail)
        days, cutoff = self._stale_days, self._stale_cutoff
        reviewed = rule_freshness(rule)
        if reviewed is None or reviewed < cutoff:
            detail = f'Last reviewed {reviewed.strftime(_REVIEWED_DATE)}' if reviewed else ''
            return CardRule(rule.id, text, 'stale', f'Not reviewed in {days} days', detail)
        if state is None:
            return CardRule(rule.id, text, 'unchecked', _RULE_LABELS['unchecked'], '')
        return CardRule(rule.id, text, 'intact', _RULE_LABELS['intact'], self._check_detail(state))

    @staticmethod
    def _check_detail(state) -> str:
        parts = []
        if state.get('checked_display'):
            parts.append(f'Checked {state["checked_display"]}')
        source = next(iter(state.get('sources') or []), None)
        if source and source.get('title'):
            parts.append(source_text(source))
        elif state.get('display_summary'):
            parts.append(state['display_summary'])
        return ' · '.join(parts)

    # Cards

    def _card_checkpoint(self, cp) -> CardCheckpoint:
        state = _checkpoint_state(cp, self._today)
        ai_status = ai_label = None
        if cp.status == 'Active':
            insight = self.alerts.checkpoint_insights.get(cp.id)
            ai_status = ((insight.supporting_data or {}).get('status_assessment')) if insight else None
            ai_label = ai_status.replace('_', ' ').capitalize() if ai_status else None
        return CardCheckpoint(cp.id, cp.target_date, cp.metric or '', cp.expectation or '', state,
                              _STATE_LABELS[state], ai_status, ai_label, state == 'overdue')

    def _card(self, row) -> PositionCard:
        company, position = row.company, row.position
        timeline = sorted(self._checkpoints_by_company.get(company.id, []),
                          key=lambda c: (c.status != 'Active', c.target_date, c.id))
        checkpoints = [self._card_checkpoint(cp) for cp in timeline]
        rules = [self._card_rule(rule) for rule in row.rules]

        flags = {gap.type for gap in row.gaps}
        statuses = {r.status for r in rules}
        alerting = {(self.alerts.rule_states.get(r.id) or {}).get('status')
                    for r in rules if _alerting(self.alerts.rule_states.get(r.id))}
        if 'triggered' in alerting:
            flags.add('triggered')
        if 'held' in statuses:
            flags.add('held')
        if any(c.state == 'overdue' for c in checkpoints):
            flags.add('overdue')
        if 'at_risk' in alerting or any(c.ai_status in _AT_RISK_ASSESSMENTS for c in checkpoints):
            flags.add('at_risk')
        ranks = [rank for flag, rank in _RANKS.items() if flag in flags]
        badges = [Badge(label, tone) for key, label, tone in _BADGES if key in flags]

        imported = self._trades.get(company.id, (False, None))[0]
        shares = int(position.total_shares or 0)
        pct = position.unrealized_gain_loss_pct
        return PositionCard(
            company.id, company.ticker_symbol or '', company.name or '', shares,
            _held_label(shares, position.days_held, imported),
            float(pct) if pct is not None else None, _one_line(self._theses.get(company.id)),
            badges, checkpoints, rules, min(ranks) if ranks else None, list(row.gaps))

    @cached_property
    def _cards(self) -> list:
        cards = [self._card(row) for row in self.alerts.coverage]
        cards.sort(key=lambda c: (c.rank is None, c.rank or 0, c.name.lower()))
        return cards

    def cards(self) -> list:
        return self._cards

    def collapse_healthy(self) -> bool:
        if len(self.alerts.coverage) <= HEALTHY_COLLAPSE_THRESHOLD:
            return False
        cards = self.cards()
        return any(c.has_problems for c in cards) and any(not c.has_problems for c in cards)

    # Metrics

    def metrics(self) -> list:
        data = self.alerts.checkpoints_data
        held_rules = [(rule, self.alerts.rule_states.get(rule.id))
                      for row in self.alerts.coverage for rule in row.rules]
        triggered = sum(1 for _, s in held_rules
                        if _alerting(s) and s.get('status') == 'triggered')
        held_through = sum(1 for _, s in held_rules
                           if ((s or {}).get('episode') or {}).get('response') == 'held'
                           and not _alerting(s))
        needs = len(self.lane())
        overdue = len(data.get('overdue', []))
        due_30 = len(data.get('this_week', [])) + len(data.get('this_month', []))
        active = [cp for group in data.values() for cp in group]
        covered = sum(1 for row in self.alerts.coverage
                      if row.has_exit_plan and row.has_future_checkpoint)
        total = len(self.alerts.coverage)
        return [
            Metric('needs_action', 'Needs action', str(needs), 'see the list below',
                   'exclamation-triangle', 'danger' if needs else 'success'),
            Metric('exit_triggered', 'Exit rules triggered', str(triggered),
                   f'{held_through} more held through' if held_through else '',
                   'box-arrow-right', 'danger' if triggered else 'neutral'),
            Metric('overdue', 'Overdue', str(overdue), 'checkpoints', 'calendar-x',
                   'danger' if overdue else 'neutral'),
            Metric('next_30_days', 'Next 30 days', str(due_30), 'checkpoints due',
                   'calendar-event', 'warning' if due_30 else 'neutral'),
            Metric('covered', 'Positions covered', f'{covered} of {total}', 'exit plan + future checkpoint',
                   'shield-check', 'success' if covered == total else 'warning'),
            Metric('active_checkpoints', 'Active checkpoints', str(len(active)),
                   f'across {_plural(len({cp.company_id for cp in active}), "position")}',
                   'flag', 'neutral'),
        ]

    # Date buckets

    def date_buckets(self) -> list:
        data = self.alerts.checkpoints_data
        merged = sorted(data.get('this_week', []) + data.get('this_month', []),
                        key=lambda cp: (cp.target_date, cp.id))
        buckets = [DateBucket('overdue', 'Overdue', data.get('overdue', [])),
                   DateBucket('next_30_days', 'Next 30 days', merged),
                   DateBucket('next_3_months', 'Next 3 months', data.get('next_3_months', [])),
                   DateBucket('later', 'Later', data.get('beyond', []))]
        return [bucket for bucket in buckets if bucket.items]

    # Not held

    def not_held(self) -> list:
        grouped = {cid: cps for cid, cps in self._checkpoints_by_company.items()
                   if cid not in self._held_ids}
        if not grouped:
            return []
        closed = {p.company_id: p.last_transaction_date for p in PortfolioPosition.query.filter(
            PortfolioPosition.user_id == self.user_id, PortfolioPosition.company_id.in_(grouped),
            PortfolioPosition.is_active.is_(False))}
        out = []
        for company_id, cps in grouped.items():
            company = cps[0].company
            sell_date = self._trades.get(company_id, (False, None))[1]
            if company_id not in closed and sell_date is None:
                continue  # never held
            sold_on = sell_date or closed.get(company_id)
            out.append(NotHeld(
                company_id, company.ticker_symbol or '', company.name or '', sold_on,
                sum(1 for c in cps if c.status == 'Met'),
                sum(1 for c in cps if c.status == 'Not Met'),
                sum(1 for c in cps if c.status == 'Active')))
        out.sort(key=lambda n: n.name.lower())
        return out
