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
Portfolio Utilities
Reusable calculation functions for portfolio analytics and metrics.
"""

from decimal import Decimal
from typing import List, Dict, Mapping


def trading_gain_loss(position) -> Decimal:
    """
    Trading result of a position: realized gain/loss with dividends taken out.

    ``realized_gain_loss`` on a position includes dividends received, so a
    sale below cost can look like a profit. Win/loss is judged on this value.
    """
    realized = position.realized_gain_loss or Decimal('0')
    dividends = position.total_dividends or Decimal('0')
    return realized - dividends


def categorize_by_holding_period(positions: List, returns: Mapping) -> Dict[str, List[float]]:
    """
    Categorize positions by holding period buckets.

    Args:
        positions: List of PortfolioPosition objects
        returns: position_returns() for these positions, keyed by company_id;
                 positions without a return are skipped

    Returns:
        Dictionary with holding period buckets as keys and return lists as values

    Example:
        >>> categorize_by_holding_period(positions, position_returns(positions))
        {
            '0-30': [5.2, 3.1],
            '31-90': [12.5, -2.3, 8.7],
            '91-180': [15.2],
            ...
        }
    """
    buckets = {
        '0-30': [],
        '31-90': [],
        '91-180': [],
        '181-365': [],
        '365+': []
    }

    for position in positions:
        measured = returns.get(position.company_id)
        if measured is None:
            continue

        days = measured.days
        return_pct = measured.total_return_pct

        if days <= 30:
            buckets['0-30'].append(return_pct)
        elif days <= 90:
            buckets['31-90'].append(return_pct)
        elif days <= 180:
            buckets['91-180'].append(return_pct)
        elif days <= 365:
            buckets['181-365'].append(return_pct)
        else:
            buckets['365+'].append(return_pct)

    return buckets


def categorize_confidence_level(confidence_score: int) -> str:
    """
    Categorize confidence score into low/medium/high.

    Args:
        confidence_score: Confidence score (1-10)

    Returns:
        Category: 'low', 'medium', or 'high'

    Example:
        >>> categorize_confidence_level(3)
        'low'
        >>> categorize_confidence_level(8)
        'high'
    """
    if confidence_score <= 4:
        return 'low'
    elif confidence_score <= 7:
        return 'medium'
    else:
        return 'high'


def categorize_by_confidence(journals_with_returns: List[Dict]) -> Dict[str, List[float]]:
    """
    Categorize positions by confidence level.

    Args:
        journals_with_returns: List of dicts with 'confidence' and 'return' keys

    Returns:
        Dictionary with confidence levels and return lists

    Example:
        >>> data = [
        ...     {'confidence': 3, 'return': 5.2},
        ...     {'confidence': 8, 'return': 15.3}
        ... ]
        >>> categorize_by_confidence(data)
        {'low': [5.2], 'medium': [], 'high': [15.3]}
    """
    buckets = {
        'low': [],      # 1-4
        'medium': [],   # 5-7
        'high': []      # 8-10
    }

    for item in journals_with_returns:
        conf = item.get('confidence')
        ret = item.get('return')

        if conf is None or ret is None:
            continue

        category = categorize_confidence_level(conf)
        buckets[category].append(ret)

    return buckets


def calculate_confidence_stats(journals_with_returns: List[Dict]) -> Dict[str, Dict]:
    """
    Calculate statistics for each confidence level.

    Args:
        journals_with_returns: List of dicts with 'confidence' and 'return' keys

    Returns:
        Dictionary with confidence levels and their stats

    Example:
        >>> calculate_confidence_stats(data)
        {
            'low': {'avg_return': 5.2, 'count': 1},
            'medium': {'avg_return': 0, 'count': 0},
            'high': {'avg_return': 15.3, 'count': 1}
        }
    """
    buckets = categorize_by_confidence(journals_with_returns)

    stats = {}
    for level, returns in buckets.items():
        avg = sum(returns) / len(returns) if returns else 0.0
        stats[level] = {
            'avg_return': round(avg, 1),
            'count': len(returns)
        }

    return stats


def process_win_rate(good_outcomes: int, bad_outcomes: int) -> float:
    """Share of research-backed positions that gained, in percent (0 when there are none)."""
    total = good_outcomes + bad_outcomes
    return good_outcomes / total * 100 if total else 0.0

