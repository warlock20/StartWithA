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

"""Conviction helpers: current thesis per company and the unrated-position summary."""

from sqlalchemy.orm import load_only

from app.models import ThesisEvolution


def current_theses(user_id, company_ids, full=False):
    """Current thesis per company: the is_current row, else the highest version.

    By default only the columns needed to rank and rate are loaded; pass
    full=True when the caller needs the whole row (thesis text, cases).
    """
    company_ids = list(company_ids)
    if not company_ids:
        return {}
    query = ThesisEvolution.query.filter(
        ThesisEvolution.user_id == user_id,
        ThesisEvolution.company_id.in_(company_ids),
    )
    if not full:
        query = query.options(load_only(
            ThesisEvolution.id, ThesisEvolution.company_id, ThesisEvolution.version,
            ThesisEvolution.is_current, ThesisEvolution.conviction_level))
    rows = query.all()
    best = {}
    for row in rows:
        # Rank: flagged current first, then higher version, then newer id
        rank = (bool(row.is_current), row.version or 0, row.id)
        held = best.get(row.company_id)
        if held is None or rank > held[0]:
            best[row.company_id] = (rank, row)
    return {cid: pair[1] for cid, pair in best.items()}


def conviction_summary(positions, theses):
    """Counts and money share of active positions with no conviction score."""
    active = [p for p in positions if p.is_active]
    total_value = 0
    unrated_value = 0
    unrated_count = 0
    for pos in active:
        thesis = theses.get(pos.company_id)
        value = float(pos.current_value or 0)
        total_value += value
        if thesis is None or thesis.conviction_level is None:
            unrated_count += 1
            unrated_value += value
    pct = round(unrated_value / total_value * 100) if total_value else 0
    return {
        'unrated_count': unrated_count,
        'total_count': len(active),
        'unrated_value_pct': pct,
    }
