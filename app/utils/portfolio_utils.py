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

from typing import List, Optional, Dict
from decimal import Decimal


def calculate_win_rate(positions: List) -> float:
    """
    Calculate win rate (percentage of profitable positions).

    Args:
        positions: List of PortfolioPosition objects

    Returns:
        Win rate as percentage (0-100)

    Example:
        >>> positions = [pos1, pos2, pos3]  # 2 winners, 1 loser
        >>> calculate_win_rate(positions)
        66.7
    """
    if not positions:
        return 0.0

    winning = sum(
        1 for p in positions
        if p.unrealized_gain_loss and p.unrealized_gain_loss > 0
    )

    return round((winning / len(positions)) * 100, 1)


def calculate_average_return(positions: List) -> float:
    """
    Calculate average return percentage across positions.

    Args:
        positions: List of PortfolioPosition objects

    Returns:
        Average return percentage

    Example:
        >>> positions = [pos1, pos2, pos3]  # Returns: 10%, 20%, -5%
        >>> calculate_average_return(positions)
        8.3
    """
    if not positions:
        return 0.0

    returns = [
        float(p.unrealized_gain_loss_pct)
        for p in positions
        if p.unrealized_gain_loss_pct is not None
    ]

    if not returns:
        return 0.0

    return round(sum(returns) / len(returns), 1)


def filter_positions_by_performance(
    positions: List,
    filter_type: str = 'all'
) -> List:
    """
    Filter positions by performance (gains/losses).

    Args:
        positions: List of PortfolioPosition objects
        filter_type: 'all', 'gains', or 'losses'

    Returns:
        Filtered list of positions

    Example:
        >>> all_positions = [winner1, winner2, loser1]
        >>> filter_positions_by_performance(all_positions, 'gains')
        [winner1, winner2]
    """
    if filter_type == 'gains':
        return [
            p for p in positions
            if p.unrealized_gain_loss and p.unrealized_gain_loss > 0
        ]
    elif filter_type == 'losses':
        return [
            p for p in positions
            if p.unrealized_gain_loss and p.unrealized_gain_loss < 0
        ]
    else:  # 'all'
        return positions


def calculate_average_holding_period(positions: List) -> int:
    """
    Calculate average holding period in days.

    Args:
        positions: List of PortfolioPosition objects

    Returns:
        Average days held (rounded to nearest day)

    Example:
        >>> positions = [pos1, pos2, pos3]  # Held: 30, 60, 90 days
        >>> calculate_average_holding_period(positions)
        60
    """
    if not positions:
        return 0

    days_list = [p.days_held for p in positions if p.days_held]

    if not days_list:
        return 0

    return round(sum(days_list) / len(days_list))


def categorize_by_holding_period(positions: List) -> Dict[str, List[float]]:
    """
    Categorize positions by holding period buckets.

    Args:
        positions: List of PortfolioPosition objects

    Returns:
        Dictionary with holding period buckets as keys and return lists as values

    Example:
        >>> categorize_by_holding_period(positions)
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
        if not position.unrealized_gain_loss_pct:
            continue

        days = position.days_held or 0
        return_pct = float(position.unrealized_gain_loss_pct)

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


def calculate_holding_period_stats(positions: List) -> Dict[str, float]:
    """
    Calculate average returns for each holding period bucket.

    Args:
        positions: List of PortfolioPosition objects

    Returns:
        Dictionary with period as key and average return as value

    Example:
        >>> calculate_holding_period_stats(positions)
        {'0-30': 4.2, '31-90': 10.5, '91-180': 15.2, ...}
    """
    buckets = categorize_by_holding_period(positions)

    stats = {}
    for period, returns in buckets.items():
        avg = sum(returns) / len(returns) if returns else 0.0
        stats[period] = round(avg, 1)

    return stats


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


def count_positions_by_status(positions: List) -> Dict[str, int]:
    """
    Count positions by gain/loss status.

    Args:
        positions: List of PortfolioPosition objects

    Returns:
        Dictionary with 'winning', 'losing', 'total' counts

    Example:
        >>> count_positions_by_status(positions)
        {'winning': 5, 'losing': 2, 'total': 7}
    """
    winning = sum(
        1 for p in positions
        if p.unrealized_gain_loss and p.unrealized_gain_loss > 0
    )

    losing = sum(
        1 for p in positions
        if p.unrealized_gain_loss and p.unrealized_gain_loss < 0
    )

    return {
        'winning': winning,
        'losing': losing,
        'total': len(positions)
    }


def get_top_performers(positions: List, limit: int = 5) -> List:
    """
    Get top performing positions.

    Args:
        positions: List of PortfolioPosition objects
        limit: Number of top performers to return

    Returns:
        List of top performers sorted by return percentage (descending)

    Example:
        >>> get_top_performers(positions, limit=3)
        [best_position, second_best, third_best]
    """
    positions_with_returns = [
        p for p in positions
        if p.unrealized_gain_loss_pct is not None
    ]

    sorted_positions = sorted(
        positions_with_returns,
        key=lambda p: p.unrealized_gain_loss_pct,
        reverse=True
    )

    return sorted_positions[:limit]


def get_bottom_performers(positions: List, limit: int = 5) -> List:
    """
    Get bottom performing positions.

    Args:
        positions: List of PortfolioPosition objects
        limit: Number of bottom performers to return

    Returns:
        List of bottom performers sorted by return percentage (ascending)

    Example:
        >>> get_bottom_performers(positions, limit=3)
        [worst_position, second_worst, third_worst]
    """
    positions_with_returns = [
        p for p in positions
        if p.unrealized_gain_loss_pct is not None
    ]

    sorted_positions = sorted(
        positions_with_returns,
        key=lambda p: p.unrealized_gain_loss_pct
    )

    return sorted_positions[:limit]
