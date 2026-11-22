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

"""App-figures snapshot sent to the model as citable evidence for an exit-criteria check."""
import logging
import math

from celery.exceptions import SoftTimeLimitExceeded

from app.services.ai.prompt_service import prompt_service
from app.services.financial_data.financial_data_service import FinancialDataService
from app.utils.time_utils import days_between, ensure_timezone_aware, now_utc

logger = logging.getLogger(__name__)

STALE_PRICE_DAYS = 3
_LABEL_KEYS = {'price': 'label_price', 'market_cap': 'label_market_cap',
               'enterprise_value': 'label_enterprise_value', 'pe_trailing': 'label_pe_trailing',
               'pe_forward': 'label_pe_forward', 'drop_from_cost_pct': 'label_drop_from_cost_pct'}


def _texts():
    return prompt_service.get_prompt_data('exit_criteria', 'exit_criteria_check')


def _safe(call, ticker, what):
    try:
        return call(ticker)
    except SoftTimeLimitExceeded:
        raise
    except Exception:
        logger.warning('exit watch: %s failed for %s', what, ticker, exc_info=True)
        return None


def _num(value):
    try:
        number = float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    return number if number is not None and math.isfinite(number) else None


def _display(item):
    value = item['value']
    if item['unit'] == '%':
        return f'{value:,.1f}' if abs(value) >= 1 else f'{value:,.2f}'
    return f'{value:,.2f}'


def build_snapshot(position, company, service=None, now=None):
    """Figures the model may cite, in a fixed order, leaving out any that are unavailable."""
    now = now or now_utc()
    today = now.date().isoformat()
    service = service or FinancialDataService()
    ticker = company.ticker_symbol
    texts = _texts()
    watch = _safe(service.get_watch_metrics, ticker, 'watch metrics') or {}
    valuation = _safe(service.get_valuation_metrics, ticker, 'valuation metrics') or {}

    items = []

    def add(field, value, unit, as_of=today, stale=False):
        value = _num(value)
        if value is None:
            return
        items.append({'id': f'A{len(items) + 1}', 'field': field,
                      'label': texts[_LABEL_KEYS[field]], 'value': value, 'unit': unit,
                      'as_of': as_of, 'stale': stale})

    updated = ensure_timezone_aware(position.last_price_update)
    stored_as_of = updated.date().isoformat() if updated else None
    stored_stale = days_between(updated, now) > STALE_PRICE_DAYS if updated else False

    price = _num(watch.get('price'))
    if price is not None and price > 0:
        add('price', price, watch.get('currency') or position.currency)
    else:
        stored = _num(position.current_price)
        if stored is not None and stored > 0 and updated is not None:
            add('price', stored, position.currency, as_of=stored_as_of, stale=stored_stale)
    add('market_cap', watch.get('market_cap'), watch.get('currency'))
    add('enterprise_value', watch.get('enterprise_value'), watch.get('currency'))
    add('pe_trailing', valuation.get('pe_ratio'), 'x')
    add('pe_forward', valuation.get('forward_pe'), 'x')

    cost, current = _num(position.average_cost_basis_base), _num(position.current_price_base)
    if cost and current and updated is not None:
        change = (current / cost - 1) * 100
        add('drop_from_cost_pct', round(change, 1) if abs(change) >= 1 else round(change, 2), '%',
            as_of=stored_as_of, stale=stored_stale)
    return items


def snapshot_text(snapshot):
    texts = _texts()
    if not snapshot:
        return texts['no_figures']
    lines = []
    for item in snapshot:
        line = texts['figure_line'].format(**{**item, 'value': _display(item)})
        if item['stale']:
            line += texts['stale_marker']
        lines.append(line)
    return '\n'.join(lines)


def valid_app_citations(cited, snapshot):
    """Ids of cited figures that exist and whose cited value matches the snapshot."""
    by_id = {item['id']: item['value'] for item in snapshot}
    valid = []
    for citation in cited or []:
        actual = by_id.get(citation.get('id'))
        value = _num(citation.get('value'))
        if actual is None or value is None:
            continue
        if abs(value - actual) <= max(0.01, 0.005 * abs(actual)) and citation['id'] not in valid:
            valid.append(citation['id'])
    return valid
