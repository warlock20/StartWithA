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

A position is research-backed when the user has a portfolio BUY journal linked
to a research project for its company. Every other position, with no journal
or with a journal that has no linked research, is unresearched.

A position's return is its own return %: unrealized for an open position,
``realized_gain_loss_pct`` for a closed one. Positions with no return are left
out of both groups.
"""

from dataclasses import dataclass
from typing import Iterable, List, Optional, Set


def position_return_pct(position) -> Optional[float]:
    """Return % of a position: unrealized if open, realized if closed."""
    value = position.unrealized_gain_loss_pct if position.is_active else position.realized_gain_loss_pct
    return float(value) if value is not None else None


def position_gain(position) -> Optional[float]:
    """Gain/loss amount of a position: unrealized if open, realized if closed."""
    value = position.unrealized_gain_loss if position.is_active else position.realized_gain_loss
    return float(value) if value is not None else None


@dataclass
class ResearchGroup:
    positions: List

    @property
    def count(self) -> int:
        return len(self.positions)

    @property
    def avg_return(self) -> float:
        if not self.positions:
            return 0.0
        return sum(position_return_pct(p) for p in self.positions) / self.count

    @property
    def win_rate(self) -> float:
        if not self.positions:
            return 0.0
        return sum(1 for p in self.positions if (position_gain(p) or 0) > 0) / self.count * 100

    @property
    def avg_hold_days(self) -> float:
        if not self.positions:
            return 0.0
        return sum(p.days_held for p in self.positions) / self.count


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


def research_company_ids(journals: Iterable) -> Set[int]:
    return {
        j.company_id for j in journals
        if j.decision_type == 'BUY' and j.is_portfolio_decision and j.linked_research_id is not None
    }


def compare_research(positions: Iterable, journals: Iterable) -> ResearchComparison:
    researched = research_company_ids(journals)
    research, no_research = [], []
    for position in positions:
        if position_return_pct(position) is None:
            continue
        (research if position.company_id in researched else no_research).append(position)
    return ResearchComparison(ResearchGroup(research), ResearchGroup(no_research))
