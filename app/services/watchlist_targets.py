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

import logging
from decimal import Decimal, InvalidOperation
from typing import Optional

from flask import url_for

from app import db
from app.models import JournalEntry, ResearchProject
from app.models.company import Company
from app.models.research import WATCH_TARGET_METRICS, WATCH_TARGET_METRIC_LABELS
from app.services.config_service import get_config
from app.services.currency_service import CurrencyService
from app.services.financial_data import FinancialDataService
from app.utils.time_utils import add_days, ensure_timezone_aware, format_date, now_utc

logger = logging.getLogger(__name__)

NEAR_TARGET_CONFIG_KEY = 'watchlist_near_target_pct'
STALE_AFTER_DAYS = 3
MIN_TARGET_VALUE = Decimal('0.0001')  # Numeric(24,4): anything smaller rounds to 0

_TARGET_FIELDS = (
    'watch_target_metric', 'watch_target_value', 'watch_target_currency',
    'watch_last_value', 'watch_last_checked_at', 'watch_target_hit_at',
    'watch_target_dismissed_at',
)


def parse_target_value(raw: str) -> Optional[Decimal]:
    """Parse a typed target. A comma is a thousands separator when a '.' is
    present, otherwise the decimal separator. None for empty, non-numeric or below
    0.0001 (the column's precision, so a smaller value would be stored as 0)."""
    text = (raw or '').strip()
    if not text:
        return None
    text = text.replace(',', '') if '.' in text else text.replace(',', '.')
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    if not value.is_finite() or value < MIN_TARGET_VALUE:
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


def _has_ticker(project) -> bool:
    return bool(project.company and project.company.ticker_symbol)


def target_status(project, near_pct: float) -> dict:
    metric = project.watch_target_metric
    target = project.watch_target_value
    last = project.watch_last_value
    currency = project.watch_target_currency
    fall = fall_needed_pct(last, target)
    raw_fall = float((last - target) / last * 100) if last is not None and target is not None and last > 0 else None
    has_target = metric is not None and target is not None
    has_ticker = _has_ticker(project)
    checked_at = ensure_timezone_aware(project.watch_last_checked_at)

    if not has_target:
        state = 'none'
    elif last is not None and last <= target:
        state = 'hit'
    elif not has_ticker:
        # The nightly check skips companies without a ticker, so this target never updates.
        state = 'no_ticker'
    elif last is None:
        state = 'unchecked'
    elif near_pct > 0 and raw_fall is not None and 0 < raw_fall <= near_pct:
        state = 'near'
    else:
        state = 'far'

    stale = bool(has_target and has_ticker and checked_at is not None
                 and checked_at < add_days(now_utc(), -STALE_AFTER_DAYS))

    return {
        'state': state,
        'metric': metric,
        'metric_label': WATCH_TARGET_METRIC_LABELS.get(metric),
        'target': target,
        'last': last,
        'currency': currency,
        'fall_needed_pct': fall,
        'raw_fall_pct': raw_fall,
        'checked_display': format_date(checked_at, 'as of %b %d', default=None),
        'stale': stale,
        'target_display': format_watch_value(metric, target, currency) if metric else '—',
        'last_display': format_watch_value(metric, last, currency) if metric else '—',
    }


def near_target_pct(user_id: int) -> float:
    return float(get_config(NEAR_TARGET_CONFIG_KEY, user_id=user_id, default=0) or 0)


def _record_hit(project, last: Decimal) -> None:
    metric = project.watch_target_metric
    currency = project.watch_target_currency
    label = WATCH_TARGET_METRIC_LABELS[metric]
    db.session.add(JournalEntry(
        user_id=project.user_id,
        company_id=project.company_id,
        project_id=project.id,
        title='Watchlist target reached',
        entry_type='investment_action',
        sentiment='neutral',
        tags=['watchlist-target-hit', 'investment-action'],
        source='watchlist_monitor',
        content=(f'{label} reached {format_watch_value(metric, last, currency)} '
                 f'(target {format_watch_value(metric, project.watch_target_value, currency)}).'),
    ))


def _target_key(project) -> tuple:
    return (project.watch_target_metric, project.watch_target_value, project.watch_target_currency)


def _apply_fetch(project, metrics: Optional[dict], key_at_fetch: tuple) -> str:
    """Apply one ticker's fetch to one project. Returns 'hit', 'checked' or 'skipped'.

    Reloads the project first so a change made while the fetch ran (decision
    changed, target edited or removed) is never overwritten with a stale result.
    """
    db.session.refresh(project)
    if (project.decision != 'watchlist' or project.watch_target_value is None
            or _target_key(project) != key_at_fetch):
        return 'skipped'
    raw = metrics.get(project.watch_target_metric) if metrics else None
    if raw is None or metrics.get('currency') != project.watch_target_currency:
        return 'skipped'
    last = Decimal(str(raw))
    project.watch_last_value = last
    project.watch_last_checked_at = now_utc()
    if project.watch_target_hit_at is None and last <= project.watch_target_value:
        project.watch_target_hit_at = now_utc()
        _record_hit(project, last)
        return 'hit'
    return 'checked'


def check_all_targets(financial_service=None) -> dict:
    """Fetch each watched ticker once and update every project's target state.

    A fetch failure, a missing/mismatched value, a project changed during the
    fetch or an error while updating one project skips that row without a hit
    and the run carries on. Commits once per ticker.
    """
    service = financial_service or FinancialDataService()
    projects = (
        ResearchProject.query.join(Company, ResearchProject.company_id == Company.id)
        .filter(
            ResearchProject.decision == 'watchlist',
            ResearchProject.watch_target_value.isnot(None),
            Company.ticker_symbol.isnot(None),
            Company.ticker_symbol != '',
        )
        .all()
    )
    by_ticker = {}
    for project in projects:
        by_ticker.setdefault(project.company.ticker_symbol, []).append(project)

    counts = {'tickers': len(by_ticker), 'checked': 0, 'hits': 0, 'skipped': 0}
    for ticker, ticker_projects in by_ticker.items():
        try:
            # Snapshot each target before the (slow) fetch to spot edits made meanwhile.
            keys = [(project.id, _target_key(project)) for project in ticker_projects]
            metrics = service.get_watch_metrics(ticker)
        except Exception:
            logger.exception('Watchlist target fetch failed for %s', ticker)
            db.session.rollback()
            counts['skipped'] += len(ticker_projects)
            continue

        tally = {'checked': 0, 'hits': 0, 'skipped': 0}
        for project, (project_id, key) in zip(ticker_projects, keys):
            try:
                with db.session.begin_nested():
                    outcome = _apply_fetch(project, metrics, key)
            except Exception:
                logger.exception('Watchlist target update failed for project %s (%s)',
                                 project_id, ticker)
                outcome = 'skipped'
            if outcome == 'skipped':
                tally['skipped'] += 1
            else:
                tally['checked'] += 1
                tally['hits'] += outcome == 'hit'

        try:
            db.session.commit()
        except Exception:
            logger.exception('Watchlist target commit failed for %s', ticker)
            db.session.rollback()
            counts['skipped'] += len(ticker_projects)
            continue
        for key, value in tally.items():
            counts[key] += value

    return counts


def active_hits(user_id: int) -> list:
    """Watchlist projects whose target was hit and not yet dismissed, newest first."""
    return (
        ResearchProject.query
        .filter(
            ResearchProject.user_id == user_id,
            ResearchProject.decision == 'watchlist',
            ResearchProject.watch_target_hit_at.isnot(None),
            ResearchProject.watch_target_dismissed_at.is_(None),
        )
        .order_by(ResearchProject.watch_target_hit_at.desc())
        .all()
    )


def near_targets(user_id: int, near_pct: float) -> list:
    """Watchlist projects not yet hit whose target_status is 'near' (the value must
    fall at most near_pct to reach the target), closest first. Empty when near_pct <= 0."""
    if near_pct <= 0:
        return []
    projects = (
        ResearchProject.query
        .filter(
            ResearchProject.user_id == user_id,
            ResearchProject.decision == 'watchlist',
            ResearchProject.watch_target_value.isnot(None),
            ResearchProject.watch_last_value.isnot(None),
            ResearchProject.watch_target_hit_at.is_(None),
        )
        .all()
    )
    ranked = []
    for project in projects:
        # Same rule as the watchlist table's "Close" badge, so both always agree.
        status = target_status(project, near_pct)
        if status['state'] == 'near':
            ranked.append((status['raw_fall_pct'], project))
    ranked.sort(key=lambda pair: pair[0])
    return [project for _, project in ranked]


def alert_item(project, near_pct: float) -> dict:
    """target_status plus the name, hit date and URLs the alert strips need.

    `recovered` is True when the target was hit but the value has since risen
    back above it, so the alert says "reached on <date>" instead of "is at or below".
    """
    item = target_status(project, near_pct)
    item.update({
        'company_name': project.subject_display_name,
        'hit_at': project.watch_target_hit_at,
        'hit_date_display': format_date(project.watch_target_hit_at, '%b %d'),
        'recovered': (project.watch_target_hit_at is not None and item['last'] is not None
                      and item['target'] is not None and item['last'] > item['target']),
        'project_url': url_for('research_workflow.project_dashboard', project_id=project.id),
        'dismiss_url': url_for('research_workflow.dismiss_watch_target', project_id=project.id),
    })
    return item
