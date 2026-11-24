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

"""Research analytics over trades (#439), one definition for every page.

A trade is a round trip (0 shares to 0 shares), see ``decision_trades``. Its research
class comes from ``classify_research``: 'none' (no project), 'low' (a project with no
score or a score under HIGH_QUALITY_RESEARCH_SCORE) or 'high'. "Research-backed" means
low or high. This module is pure: it takes the trades a caller built and splits them.

Limitations: a trade's return leaves out dividends, and the class is the project and
score stored on the outcome at its last sync (see ``decision_trades``).
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.constants import HIGH_QUALITY_RESEARCH_SCORE, MIN_TRADES_FOR_RESEARCH_SUMMARY


def classify_research(outcome) -> str:
    """
    The research class of a trade: 'none', 'low' or 'high'.

    No project is 'none'. A project with no score yet (researched, ungraded) or a
    score below HIGH_QUALITY_RESEARCH_SCORE is 'low'. Reads the values stored on the
    outcome at its last sync, not the project's score now.
    """
    if outcome.project_id is None:
        return 'none'
    score = outcome.research_quality_score
    if score is None or score < HIGH_QUALITY_RESEARCH_SCORE:
        return 'low'
    return 'high'


SCOPES = ('all', 'closed')


def in_scope(trades: List, scope: str) -> List:
    """'all' keeps every trade, 'closed' only the ones that are closed."""
    if scope == 'all':
        return list(trades)
    if scope == 'closed':
        return [t for t in trades if t.is_closed]
    raise ValueError(f'Unknown scope: {scope!r}')


@dataclass
class TradeGroup:
    trades: List

    @property
    def count(self) -> int:
        return len(self.trades)

    @property
    def avg_return(self) -> float:
        if not self.trades:
            return 0.0
        return sum(t.return_pct for t in self.trades) / self.count

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        return sum(1 for t in self.trades if t.is_gain) / self.count * 100

    @property
    def avg_hold_days(self) -> float:
        if not self.trades:
            return 0.0
        return sum(t.days for t in self.trades) / self.count


@dataclass
class ResearchComparison:
    none: TradeGroup
    low: TradeGroup
    high: TradeGroup
    research: TradeGroup  # low and high trades together

    @property
    def edge(self) -> Optional[float]:
        """Research avg return minus no-research avg return; None if either side is empty."""
        if not (self.research.count and self.none.count):
            return None
        return self.research.avg_return - self.none.avg_return

    @property
    def quality_edge(self) -> Optional[float]:
        """High-research avg return minus low-research avg return; None if either is empty."""
        if not (self.high.count and self.low.count):
            return None
        return self.high.avg_return - self.low.avg_return


def compare_research(trades: List) -> ResearchComparison:
    """Split trades by research class (their ``research`` attribute)."""
    by_class = {'none': [], 'low': [], 'high': []}
    for trade in trades:
        by_class[trade.research].append(trade)
    return ResearchComparison(
        none=TradeGroup(by_class['none']),
        low=TradeGroup(by_class['low']),
        high=TradeGroup(by_class['high']),
        research=TradeGroup(by_class['low'] + by_class['high']),
    )


GRADES = ('A', 'B', 'C', 'D', 'F')


@dataclass
class GradeRow:
    grade: str
    group: TradeGroup


def grade_table(trades: List) -> Tuple[List[GradeRow], int]:
    """
    One row per letter grade (A to F, empty rows kept) over the researched trades.

    The second value counts researched trades that have no score yet, so they are
    in no row. Trades with no research are left out.
    """
    by_grade = {grade: [] for grade in GRADES}
    unscored = 0
    for trade in trades:
        if trade.research == 'none':
            continue
        if trade.grade is None:
            unscored += 1
        else:
            by_grade[trade.grade].append(trade)
    return [GradeRow(grade, TradeGroup(by_grade[grade])) for grade in GRADES], unscored


@dataclass
class QualitySummary:
    edge: Optional[float]   # high-quality avg return minus low-quality avg return
    n: int                  # trades behind it (high plus low)
    small_sample: bool


def quality_summary(trades: List) -> QualitySummary:
    comparison = compare_research(trades)
    n = comparison.high.count + comparison.low.count
    return QualitySummary(
        edge=comparison.quality_edge,
        n=n,
        small_sample=n < MIN_TRADES_FOR_RESEARCH_SUMMARY,
    )


def research_quality_view(trades: List) -> Dict[str, dict]:
    """Everything the Research quality section shows, per scope ('all' and 'closed')."""
    view = {}
    for scope in SCOPES:
        scoped = in_scope(trades, scope)
        grades, unscored = grade_table(scoped)
        view[scope] = {
            'comparison': compare_research(scoped),
            'grades': grades,
            'unscored': unscored,
            'summary': quality_summary(scoped),
            'count': len(scoped),
        }
    return view
