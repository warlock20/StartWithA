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

"""Deterministic metrics for /portfolio/analytics (issue #347).

``build_portfolio_analytics`` is the single source of the page's numbers; the
route and template render its dict as-is.
"""

from datetime import date
from typing import Any, Dict, List, Optional

from app.services.portfolio_data_extractor import PortfolioDataExtractor

UNKNOWN_SECTOR = 'Unknown'
UNCLASSIFIED_LABEL = 'Unclassified'


def strategy_label(avg_hold_days: float) -> str:
    """Get strategy label based on holding period"""
    if avg_hold_days < 30:
        return "Short-term Trading"
    elif avg_hold_days < 90:
        return "Medium-term Strategy"
    else:
        return "Long-term Strategy"


def disposition_insight(patterns: Dict[str, Any]) -> Optional[str]:
    """Generate disposition effect insight"""
    winner_days = patterns.get("avg_winner_hold_days", 0)
    loser_days = patterns.get("avg_loser_hold_days", 0)

    if winner_days and loser_days > winner_days * 1.2:
        pct_longer = round(((loser_days - winner_days) / winner_days) * 100)
        return f"You hold losers {pct_longer}% longer than winners."
    return None


def sector_concentration(sector_breakdown: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Largest classified sector; 'Unknown' is reported separately, never as a sector."""
    classified = [r for r in sector_breakdown if r['sector'] != UNKNOWN_SECTOR]
    unknown = next((r for r in sector_breakdown if r['sector'] == UNKNOWN_SECTOR), None)
    largest = max(classified, key=lambda r: r['percentage'], default=None)
    return {
        'largest_sector': largest['sector'] if largest else None,
        'largest_sector_pct': largest['percentage'] if largest else None,
        'unclassified_pct': unknown['percentage'] if unknown else 0.0,
    }


def build_portfolio_analytics(user_id: int, as_of: Optional[date] = None) -> Dict[str, Any]:
    data = PortfolioDataExtractor(user_id).extract_all(as_of=as_of)
    summary = data['portfolio_summary']
    patterns = data['trading_patterns']
    breakdown = data['sector_breakdown']
    concentration = sector_concentration(breakdown)
    avg_hold_days = round(patterns.get('avg_hold_days', 0))

    sectors = [
        {**row, 'sector': UNCLASSIFIED_LABEL if row['sector'] == UNKNOWN_SECTOR else row['sector']}
        for row in breakdown
    ]

    return {
        'has_data': data['metadata']['has_data'],
        'transactions_count': summary.get('total_transactions', 0),
        'positions_count': summary.get('total_positions', 0),
        'kpis': {
            'win_rate': summary.get('win_rate', 0),
            'wins': summary.get('wins', 0),
            'losses': summary.get('losses', 0),
            'xirr': summary.get('xirr'),
            'cagr': summary.get('cagr', 0),
            'avg_hold_days': avg_hold_days,
            'strategy_label': strategy_label(avg_hold_days),
            'positions_count': summary.get('total_positions', 0),
            'largest_sector': concentration['largest_sector'],
            'largest_sector_pct': concentration['largest_sector_pct'],
        },
        'unclassified_pct': concentration['unclassified_pct'],
        'sectors': sectors,
        'comparison': {
            'winners': {
                'count': summary.get('wins', 0),
                'avg_return': round(patterns.get('avg_winner_return', 0), 1),
                'hold_time': round(patterns.get('avg_winner_hold_days', 0)),
            },
            'losers': {
                'count': summary.get('losses', 0),
                'avg_loss': round(patterns.get('avg_loser_return', 0), 1),
                'hold_time': round(patterns.get('avg_loser_hold_days', 0)),
                'insight': disposition_insight(patterns),
            },
        },
    }
