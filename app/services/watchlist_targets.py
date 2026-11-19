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

"""Watchlist valuation targets: parsing, setting, clearing and status."""

from decimal import Decimal, InvalidOperation
from typing import Optional

from app.models.research import WATCH_TARGET_METRICS, WATCH_TARGET_METRIC_LABELS
from app.services.config_service import get_config
from app.services.currency_service import CurrencyService

NEAR_TARGET_CONFIG_KEY = 'watchlist_near_target_pct'

_TARGET_FIELDS = (
    'watch_target_metric', 'watch_target_value', 'watch_target_currency',
    'watch_last_value', 'watch_last_checked_at', 'watch_target_hit_at',
    'watch_target_dismissed_at',
)


def parse_target_value(raw: str) -> Optional[Decimal]:
    """Parse a typed target. A comma is a thousands separator when a '.' is
    present, otherwise the decimal separator. None for empty, non-numeric or <= 0."""
    text = (raw or '').strip()
    if not text:
        return None
    text = text.replace(',', '') if '.' in text else text.replace(',', '.')
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    if not value.is_finite() or value <= 0:
        return None
    return value


def set_target(project, metric: str, value: Decimal, currency: str) -> None:
    """Set the target and re-arm it. Keeps the last fetched value. Does not commit."""
    if metric not in WATCH_TARGET_METRICS:
        raise ValueError(f'Unknown watch target metric: {metric}')
    project.watch_target_metric = metric
    project.watch_target_value = value
    project.watch_target_currency = currency
    project.watch_target_hit_at = None
    project.watch_target_dismissed_at = None


def clear_target(project) -> None:
    """Remove the target and all state tied to it. Does not commit."""
    for field in _TARGET_FIELDS:
        setattr(project, field, None)


def fall_needed_pct(current: Optional[Decimal], target: Optional[Decimal]) -> Optional[float]:
    """Percent the value must fall to reach the target. Negative means already below."""
    if current is None or target is None or current <= 0:
        return None
    return round(float((current - target) / current * 100), 1)


def format_watch_value(metric: str, value: Optional[Decimal], currency: Optional[str]) -> str:
    if value is None:
        return '—'
    symbol = CurrencyService.get_currency_symbol(currency)
    if metric == 'price':
        return f'{symbol}{value:,.2f}'
    return f'{symbol}{value / Decimal(10) ** 9:,.1f}B'


def target_status(project, near_pct: float) -> dict:
    metric = project.watch_target_metric
    target = project.watch_target_value
    last = project.watch_last_value
    currency = project.watch_target_currency
    fall = fall_needed_pct(last, target)
    raw_fall = float((last - target) / last * 100) if last is not None and target is not None and last > 0 else None

    if metric is None or target is None:
        state = 'none'
    elif last is None:
        state = 'unchecked'
    elif last <= target:
        state = 'hit'
    elif near_pct > 0 and raw_fall is not None and 0 < raw_fall <= near_pct:
        state = 'near'
    else:
        state = 'far'

    return {
        'state': state,
        'metric': metric,
        'metric_label': WATCH_TARGET_METRIC_LABELS.get(metric),
        'target': target,
        'last': last,
        'currency': currency,
        'fall_needed_pct': fall,
        'target_display': format_watch_value(metric, target, currency) if metric else '—',
        'last_display': format_watch_value(metric, last, currency) if metric else '—',
    }


def near_target_pct(user_id: int) -> float:
    return float(get_config(NEAR_TARGET_CONFIG_KEY, user_id=user_id, default=0) or 0)
