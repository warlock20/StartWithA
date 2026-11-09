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

"""View model for the Mistake Log shown on the Knowledge Hub Mistakes tab."""

import re
from collections import Counter

SORTS = ('newest', 'cost', 'severity')
_TYPE_RE = re.compile(r'^[a-z_]{1,40}$')
_MIN_DATE_KEY = 0


def type_label(key):
    """'thesis_drift' -> 'Thesis Drift'."""
    return str(key).replace('_', ' ').title()


def valid_mistake_type(value):
    """The mistake type if it looks like a type key, else None."""
    return value if isinstance(value, str) and _TYPE_RE.match(value) else None


def valid_sort(value):
    return value if value in SORTS else 'newest'


def _cost(mistake):
    return mistake.cost_estimate or 0


def _created(mistake):
    return mistake.created_at.timestamp() if mistake.created_at else _MIN_DATE_KEY


def _sorted(mistakes, sort_by):
    items = sorted(mistakes, key=_created, reverse=True)  # newest first, stable base order
    if sort_by == 'cost':
        with_cost = sorted((m for m in items if m.cost_estimate is not None), key=lambda m: m.cost_estimate, reverse=True)
        return with_cost + [m for m in items if m.cost_estimate is None]
    if sort_by == 'severity':
        return sorted(items, key=lambda m: m.severity or 0, reverse=True)
    return items


def build_mistake_view(all_mistakes, visible, mistake_type, sort_by, ids_with_criteria,
                       search=None, company_filtered=False):
    """Everything the Mistakes tab renders.

    Metrics, insights and type chips cover `all_mistakes`; `visible` is the
    search/company-filtered list that the type filter and sort apply to.
    """
    mistake_type = valid_mistake_type(mistake_type)
    sort_by = valid_sort(sort_by)
    total = len(all_mistakes)

    counts = Counter(m.mistake_type for m in all_mistakes)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], type_label(kv[0])))

    most_common = None
    if ranked:
        key, count = ranked[0]
        most_common = {'key': key, 'label': type_label(key), 'count': count}

    metrics = {
        'total': total,
        'total_cost': sum(_cost(m) for m in all_mistakes),
        'most_common': most_common,
        'prevented': sum(1 for m in all_mistakes if (m.prevented_similar or 0) > 0),
        'in_checklists': sum(1 for m in all_mistakes if m.id in ids_with_criteria),
    }

    costly = sorted((m for m in all_mistakes if m.cost_estimate is not None and m.cost_estimate > 0),
                    key=lambda m: m.cost_estimate, reverse=True)[:3]
    pattern = None
    if most_common:
        key, count = ranked[0]
        pattern = {
            **most_common,
            'total': total,
            'share_pct': round(count / total * 100),
            'cost': sum(_cost(m) for m in all_mistakes if m.mistake_type == key),
            'others': [{'label': type_label(k), 'count': c} for k, c in ranked[1:]],
        }

    type_chips = [{'key': None, 'label': 'All', 'count': total, 'active': mistake_type is None}]
    type_chips += [{'key': k, 'label': type_label(k), 'count': c, 'active': k == mistake_type}
                   for k, c in ranked]

    shown = [m for m in visible if mistake_type is None or m.mistake_type == mistake_type]
    shown = _sorted(shown, sort_by)

    summary = None
    if mistake_type or search or company_filtered:
        summary = {
            'count': len(shown),
            'label': type_label(mistake_type) if mistake_type else None,
            'search': search or None,
            'cost': sum(_cost(m) for m in shown),
        }

    return {
        'metrics': metrics,
        'insights': {'costly': costly, 'pattern': pattern},
        'type_chips': type_chips,
        'mistake_type': mistake_type,
        'sort_by': sort_by,
        'list': shown,
        'filter_summary': summary,
    }
