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
Page context for the companion rail.

The rail shows a row of small pills — "chips" — naming the things the companion
is using to answer you::

    Context   [ASML]  [Kiran's Checklist]  [2 notes]

So you can see at a glance whether an answer is drawing on your ASML research or
on your whole account, without having to ask.

A page says what it's showing in ``companion_focus``, built from objects it
already renders::

    {% set companion_focus = {
        'type': 'company', 'company_id': company.id,
        'chips': [{'icon': 'bi-building', 'label': company.ticker_symbol}]} %}

This module does the small part the template can't: it normalises that
declaration, adds counts that would need a query, and supplies the account-wide
default for the ~30 pages that declare nothing yet.

Why the page declares instead of the server resolving ids into labels: the
template already holds the objects, already authorised them, and knows which of
them the user is actually looking at. Re-deriving the labels server-side would
redo that work and reintroduce the question of whether an id can be trusted.

Two rules shape the payload:

1. **It is a generic list.** Every chip is ``{icon, label, kind}`` and nothing
   else — no company/project/step-shaped fields. As more pages declare more of
   what they show, they produce more chips and the rail needs no change. That
   genericity is what lets page-declared context land page by page.
2. **Counts are filtered by ``user_id``**, so a stale or wrong ``company_id`` can
   only ever count the caller's own rows.

``kind`` is ``'mine'`` for the user's own data and ``'page'`` for what the page is
displaying; the rail styles the two differently.
"""

from app.models.journal import JournalEntry
from app.models.portfolio import PortfolioPosition

# Shown when a page declares nothing. The companion really is grounded
# account-wide there, so say that rather than inventing a page identity.
ACCOUNT_CHIP = {'icon': 'bi-globe', 'label': 'Your account', 'kind': 'mine'}


def _normalise(declared):
    """Keep declared chips to the generic shape, dropping anything unlabelled.

    A template rendering a missing attribute (no ticker, no project name) yields a
    blank label; that should collapse to no chip rather than an empty pill.
    """
    chips = []
    for chip in declared or []:
        label = str((chip or {}).get('label') or '').strip()
        if not label:
            continue
        chips.append({
            'icon': (chip.get('icon') or 'bi-dot'),
            'label': label,
            'kind': 'mine' if chip.get('kind') == 'mine' else 'page',
        })
    return chips


def _count_chip(icon, count, noun):
    if not count:
        return None
    return {'icon': icon, 'label': f"{count} {noun}{'' if count == 1 else 's'}",
            'kind': 'mine'}


def build_context_chips(user_id, focus=None):
    """Chips for the rail: what the page declared, plus counts. Never empty."""
    focus = focus or {}
    chips = _normalise(focus.get('chips'))

    company_id = focus.get('company_id')
    if company_id:
        notes = JournalEntry.query.filter_by(
            user_id=user_id, company_id=company_id).count()
        chip = _count_chip('bi-journal', notes, 'note')
        if chip:
            chips.append(chip)
    elif focus.get('type') == 'portfolio':
        holdings = PortfolioPosition.query.filter_by(
            user_id=user_id, is_active=True).count()
        chip = _count_chip('bi-pie-chart', holdings, 'holding')
        if chip:
            chips.append(chip)

    return chips or [ACCOUNT_CHIP]
