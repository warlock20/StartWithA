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

"""Research-backed vs unresearched positions, one definition for every page.

A position is research-backed when its company's latest trade outcome (highest
``decision_date``, ties by highest id) has a research project under the #417
timing rule: an explicit journal link, else a project created on or before the
trade's entry date. Every other position, including one with no outcome row, is
unresearched. The set of research-backed company ids comes from
``outcome_tracking.research_backed_company_ids``; this module stays free of DB
queries.

Limitations: for a company traded more than once, a closed position's return %
is lifetime across trades while the research flag comes from the latest trade.
Before the backfill (``flask rebuild-trade-outcomes``) runs, positions without
outcome rows count as no research.

A position's return is its lifetime return from ``position_returns``:
unrealized + realized + dividends over the capital put in, the same for open and
closed positions. The caller passes those returns in, keyed by company_id;
positions with no return are left out of both groups.
"""

from dataclasses import dataclass
from typing import Iterable, List, Mapping, Optional, Set

from app.constants import HIGH_QUALITY_RESEARCH_SCORE
from app.services.position_returns import PositionReturn


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


@dataclass
class ResearchGroup:
    positions: List
    returns: Mapping[int, PositionReturn]

    @property
    def count(self) -> int:
        return len(self.positions)

    @property
    def avg_return(self) -> float:
        if not self.positions:
            return 0.0
        return sum(self.returns[p.company_id].total_return_pct for p in self.positions) / self.count

    @property
    def win_rate(self) -> float:
        if not self.positions:
            return 0.0
        return sum(1 for p in self.positions if self.returns[p.company_id].is_gain) / self.count * 100

    @property
    def avg_hold_days(self) -> float:
        if not self.positions:
            return 0.0
        # Up to today for open positions, up to the last sale for closed ones
        return sum(self.returns[p.company_id].days for p in self.positions) / self.count


@dataclass
class ResearchComparison:
    research: ResearchGroup
    no_research: ResearchGroup

    @property
    def edge(self) -> Optional[float]:
        """Research avg return minus no-research avg return; None if either group is empty."""
        if not (self.research.count and self.no_research.count):
            return None
        return self.research.avg_return - self.no_research.avg_return


def compare_research(positions: Iterable, researched_company_ids: Set[int],
                     returns: Mapping[int, PositionReturn]) -> ResearchComparison:
    """Split positions by whether their company id is in researched_company_ids.

    returns is position_returns() for (at least) these positions. See the module
    docstring for the definition and its limitations. Companies whose every outcome is
    received (a merger or spin-off, #451) are left out by the caller.
    """
    research, no_research = [], []
    for position in positions:
        if position.company_id not in returns:
            continue
        (research if position.company_id in researched_company_ids else no_research).append(position)
    return ResearchComparison(ResearchGroup(research, returns), ResearchGroup(no_research, returns))
