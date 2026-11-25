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
Research effectiveness (#440): which checklist answers and which open red flags came
before good and bad trades.

This shows what came before an outcome, not what caused it. Numbers are plain counts
and rates over the trades from ``decision_trades`` (received holdings already out);
trades with research 'unknown' are left out everywhere.

- Checklist: per checklist item, the researched trades (research 'low' or 'high') are
  split by the verdict the user held at the buy: Concern (not satisfied, needs
  attention) vs Satisfied. Neutral answers and items with no verdict are left out.
  The verdict at the buy is the newest one (by ``verdict_at``) for that item across the
  user's checklist analyses of the company, dated on or before the opening date.
- Red flags: every trade is split by whether a red flag on the company was open at
  the buy: created on or before the opening date and not archived by then.

A finding needs both groups at MIN_GROUP_TRADES or more and a win-rate gap of
WIN_RATE_GAP_PP or an average-return gap of RETURN_GAP_PP. It is shown in either
direction. "Mark as noise" hides a finding in a scope while that scope's counts are
the ones stored with the dismissal.

Limitations:
- ``verdict_at`` on answers saved before #440 is backfilled from ``answered_at``, which
  moved on every notes autosave, so an old verdict can look newer than it is.
- A verdict changed after the buy is excluded for that trade: its old value is lost.
- ``archived_at`` on flags archived before #440 is backfilled from ``updated_at``, which
  is at or after the real archive time.
- Red flags that were hard-deleted or retyped are invisible.
- ``verdict_at``, ``created_at`` and ``archived_at`` are compared by their UTC date against the
  local trade date, so for users far from UTC an answer or flag near midnight can land on the
  other side of the buy.

Nothing here writes; it is safe on every page render.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import joinedload

from app import db
from app.models import ChecklistAnalysis, ChecklistAnswer, ChecklistItem, JournalEntry
from app.services.decision_quality import SCOPES, in_scope
from app.services.decision_trades import DecisionTrade
from app.utils.time_utils import date

MIN_GROUP_TRADES = 3
SMALL_SAMPLE_TRADES = 5
WIN_RATE_GAP_PP = 25
RETURN_GAP_PP = 10
MAX_CHECKLIST_FINDINGS = 5

RED_FLAG_KEY = 'red_flags'
RED_FLAG_TITLE = 'Red flags you bought through'
WITH_RED_FLAG = 'With an open red flag'
WITHOUT_RED_FLAG = 'No open red flag'

CONCERN = 'Concern'
SATISFIED = 'Satisfied'
# satisfaction_status -> group; a status not in the map is left out
VERDICT_GROUPS = {'not_satisfied': CONCERN, 'needs_attention': CONCERN, 'satisfied': SATISFIED}

RESEARCHED = ('low', 'high')
BETTER_WITH_RISK_NOTE = 'So far a concern here did not come before worse results.'


def checklist_key(item_id: int) -> str:
    return f'checklist_item:{item_id}'


def opening_date(trade: DecisionTrade) -> date:
    """The day the trade was opened: its opening decision's date, else its entry date."""
    if trade.opening is not None:
        return trade.opening.decision_date
    return trade.entry_date


@dataclass
class TradeHistory:
    verdicts: Dict[int, Dict[int, str]]          # outcome id -> {item_id: status held at the buy}
    items: Dict[int, ChecklistItem]
    red_flags: Dict[int, List[JournalEntry]]     # outcome id -> flags open at the buy


def _flag_open_at(flag: JournalEntry, on: date) -> bool:
    if flag.created_at is None or flag.created_at.date() > on:
        return False
    return flag.archived_at is None or flag.archived_at.date() > on


def load_history(user_id: int, trades: List[DecisionTrade]) -> TradeHistory:
    """Checklist verdicts and open red flags at each trade's opening date (two queries)."""
    company_ids = {t.company_id for t in trades}
    if not company_ids:
        return TradeHistory(verdicts={}, items={}, red_flags={})

    answers_by_company = defaultdict(list)
    items = {}
    rows = db.session.query(ChecklistAnswer, ChecklistAnalysis.company_id).join(
        ChecklistAnalysis, ChecklistAnswer.checklist_analysis_id == ChecklistAnalysis.id,
    ).filter(
        ChecklistAnalysis.user_id == user_id,
        ChecklistAnalysis.company_id.in_(company_ids),
        ChecklistAnswer.verdict_at.isnot(None),
        ChecklistAnswer.satisfaction_status.isnot(None),
    ).options(joinedload(ChecklistAnswer.item)).all()
    for answer, company_id in rows:
        answers_by_company[company_id].append(answer)
        items[answer.checklist_item_id] = answer.item
    for answers in answers_by_company.values():
        answers.sort(key=lambda a: (a.verdict_at, a.id))  # oldest first, so the newest overwrites

    flags_by_company = defaultdict(list)
    for flag in JournalEntry.query.filter(
        JournalEntry.user_id == user_id,
        JournalEntry.company_id.in_(company_ids),
        JournalEntry.entry_type == 'red_flag',
    ).all():
        flags_by_company[flag.company_id].append(flag)

    verdicts, red_flags = {}, {}
    for trade in trades:
        opened = opening_date(trade)
        held = {}
        for answer in answers_by_company[trade.company_id]:
            if answer.verdict_at.date() <= opened:
                held[answer.checklist_item_id] = answer.satisfaction_status
        verdicts[trade.outcome.id] = held
        red_flags[trade.outcome.id] = [f for f in flags_by_company[trade.company_id] if _flag_open_at(f, opened)]
    return TradeHistory(verdicts=verdicts, items=items, red_flags=red_flags)


@dataclass
class Group:
    label: str
    trades: List[DecisionTrade]

    @property
    def count(self) -> int:
        return len(self.trades)

    @property
    def wins(self) -> int:
        return sum(1 for t in self.trades if t.is_gain)

    @property
    def losses(self) -> int:
        return self.count - self.wins

    @property
    def win_rate(self) -> float:
        return self.wins / self.count * 100 if self.trades else 0.0

    @property
    def avg_return(self) -> float:
        return sum(t.return_pct for t in self.trades) / self.count if self.trades else 0.0

    @property
    def small_sample(self) -> bool:
        return self.count < SMALL_SAMPLE_TRADES


@dataclass
class Finding:
    key: str
    kind: str                  # 'checklist' | 'red_flags'
    title: str
    risk: Group                # Concern, or With an open red flag
    base: Group                # Satisfied, or No open red flag
    worse_with_risk: bool
    strength: float
    small_sample: bool
    item_id: Optional[int] = None
    flags: List[JournalEntry] = field(default_factory=list)
    counts: list = field(default_factory=list)   # [[label, trades, wins], ...] sorted by label

    @property
    def body(self) -> str:
        risk, base = self.risk, self.base
        if self.kind == 'checklist':
            return (f'You bought {risk.count} times with a concern on this item. '
                    f'{risk.losses} lost money (avg {risk.avg_return:+.1f}%). '
                    f'When satisfied: {base.wins} of {base.count} gained (avg {base.avg_return:+.1f}%).')
        return (f'You bought {risk.count} times with an open red flag. '
                f'{risk.losses} of those lost money (avg {risk.avg_return:+.1f}%). '
                f'Without one: {base.wins} of {base.count} gained.')

    @property
    def note(self) -> Optional[str]:
        """The second line, shown when the risk group did not do worse."""
        return None if self.worse_with_risk else BETTER_WITH_RISK_NOTE


@dataclass
class FindingSlot:
    kind: str                  # 'checklist' | 'red_flags'
    state: str                 # 'locked' | 'shown' | 'no_difference'
    have: int
    needed: int
    findings: List[Finding]
    hidden: int                # qualifying findings marked as noise, counts unchanged


def _finding(key: str, kind: str, title: str, risk: Group, base: Group, **extra) -> Optional[Finding]:
    """The finding when the groups differ enough, else None."""
    if risk.count < MIN_GROUP_TRADES or base.count < MIN_GROUP_TRADES:
        return None
    # Rounded so a gap of exactly the threshold (8/12 vs 5/12 is 24.999999999999986) qualifies
    win_gap = round(abs(risk.win_rate - base.win_rate), 9)
    return_gap = round(abs(risk.avg_return - base.avg_return), 9)
    if win_gap < WIN_RATE_GAP_PP and return_gap < RETURN_GAP_PP:
        return None
    return Finding(
        key=key,
        kind=kind,
        title=title,
        risk=risk,
        base=base,
        worse_with_risk=risk.avg_return < base.avg_return,
        strength=max(win_gap / WIN_RATE_GAP_PP, return_gap / RETURN_GAP_PP),
        small_sample=risk.small_sample or base.small_sample,
        counts=sorted([g.label, g.count, g.wins] for g in (risk, base)),
        **extra,
    )


def _by_strength(findings: List[Finding]) -> List[Finding]:
    return sorted(findings, key=lambda f: (-f.strength, f.key))


@dataclass
class ScopeFindings:
    checklist: List[Finding]       # every qualifying checklist finding, strongest first, uncapped
    red_flags: Optional[Finding]
    checklist_have: int            # researched trades with any checklist verdict
    red_flags_have: int            # trades bought with an open red flag


def scope_findings(trades: List[DecisionTrade], history: TradeHistory, scope: str) -> ScopeFindings:
    """Every qualifying finding in one scope, before dismissals and the cap."""
    scoped = [t for t in in_scope(trades, scope) if t.research != 'unknown']

    researched = [t for t in scoped if t.research in RESEARCHED]
    by_item = defaultdict(lambda: {CONCERN: [], SATISFIED: []})
    for trade in researched:
        for item_id, status in history.verdicts.get(trade.outcome.id, {}).items():
            group = VERDICT_GROUPS.get(status)
            if group is not None:
                by_item[item_id][group].append(trade)
    checklist = []
    for item_id, groups in by_item.items():
        item = history.items.get(item_id)
        found = _finding(
            checklist_key(item_id), 'checklist', item.text if item is not None else '',
            Group(CONCERN, groups[CONCERN]), Group(SATISFIED, groups[SATISFIED]), item_id=item_id,
        )
        if found is not None:
            checklist.append(found)

    flagged, clean = [], []
    for trade in scoped:
        (flagged if history.red_flags.get(trade.outcome.id) else clean).append(trade)
    flags = {}
    for trade in flagged:
        for flag in history.red_flags[trade.outcome.id]:
            flags[flag.id] = flag
    red = _finding(
        RED_FLAG_KEY, 'red_flags', RED_FLAG_TITLE, Group(WITH_RED_FLAG, flagged), Group(WITHOUT_RED_FLAG, clean),
        flags=sorted(flags.values(), key=lambda f: (f.created_at, f.id)),
    )

    return ScopeFindings(
        checklist=_by_strength(checklist),
        red_flags=red,
        checklist_have=sum(1 for t in researched if history.verdicts.get(t.outcome.id)),
        red_flags_have=len(flagged),
    )


def _slot(kind: str, have: int, qualifying: List[Finding], scope: str, dismissals: Dict[str, dict],
          cap: Optional[int] = None) -> FindingSlot:
    if have < MIN_GROUP_TRADES:
        return FindingSlot(kind=kind, state='locked', have=have, needed=MIN_GROUP_TRADES, findings=[], hidden=0)
    visible = [f for f in qualifying if (dismissals.get(f.key) or {}).get(scope) != f.counts]
    return FindingSlot(
        kind=kind,
        state='shown' if qualifying else 'no_difference',
        have=have,
        needed=MIN_GROUP_TRADES,
        findings=visible[:cap] if cap is not None else visible,
        hidden=len(qualifying) - len(visible),
    )


def effectiveness_view(trades: List[DecisionTrade], history: TradeHistory,
                       dismissals: Dict[str, dict]) -> Dict[str, dict]:
    """
    Per scope in SCOPES: {'checklist': FindingSlot, 'red_flags': FindingSlot, 'ranked': [Finding]}.

    ``dismissals`` maps a finding key to the counts stored when it was marked as noise
    ({'closed': [...], 'all': [...]}). A slot is 'shown' when any finding qualifies, even
    if every one is hidden (then ``findings`` is empty and ``hidden`` says how many).
    """
    view = {}
    for scope in SCOPES:
        found = scope_findings(trades, history, scope)
        checklist = _slot('checklist', found.checklist_have, found.checklist, scope, dismissals,
                          cap=MAX_CHECKLIST_FINDINGS)
        red_flags = _slot('red_flags', found.red_flags_have,
                          [found.red_flags] if found.red_flags is not None else [], scope, dismissals)
        view[scope] = {
            'checklist': checklist,
            'red_flags': red_flags,
            'ranked': _by_strength(checklist.findings + red_flags.findings),
        }
    return view


def find_finding(trades: List[DecisionTrade], history: TradeHistory,
                 key: str) -> Optional[Tuple[Finding, Dict[str, list]]]:
    """
    The qualifying finding with this key (closed scope first, then all), ignoring
    dismissals and the cap, plus its counts per scope (a scope where it does not
    qualify gets []). None when it qualifies in no scope.
    """
    per_scope = {}
    for scope in SCOPES:
        found = scope_findings(trades, history, scope)
        candidates = found.checklist + ([found.red_flags] if found.red_flags is not None else [])
        per_scope[scope] = next((f for f in candidates if f.key == key), None)
    finding = per_scope['closed'] or per_scope['all']
    if finding is None:
        return None
    return finding, {scope: (f.counts if f is not None else []) for scope, f in per_scope.items()}
