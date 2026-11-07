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

"""Shared ISIN validation and storage for a company.

Used by the company edit route and the Edit Idea page so both apply the same
rules and produce the same messages.
"""

import logging

from app import db
from app.models import Company
from app.services.sweep_link import link_from_isin
from app.utils.isin import is_valid_isin, normalize_isin

logger = logging.getLogger(__name__)


def check_company_isin(user_id, company_id, raw):
    """Normalize and validate a submitted ISIN.

    Returns (isin, error). A blank value returns (None, None), meaning
    "no ISIN". company_id is the company being edited (excluded from the
    clash check), or None.
    """
    isin = normalize_isin(raw)
    if isin is None:
        return None, None

    if not is_valid_isin(isin):
        return None, (f'"{isin}" is not a valid ISIN. It must be 12 characters '
                      f'with a correct check digit.')

    clash = Company.query.filter(
        Company.user_id == user_id,
        Company.isin == isin,
        Company.id != company_id,
    ).first()
    if clash:
        return None, f'ISIN {isin} is already assigned to {clash.name}.'

    return isin, None


def set_company_isin(user_id, company, isin):
    """Set company.isin (None clears it) and link matching sweep rows. Never commits."""
    company.isin = isin
    if isin is not None:
        # A newly-entered ISIN may match sweep rows the user has already
        # seen. Those links are secondary to saving the company, so a
        # savepoint contains any failure here. begin_nested() flushes
        # first, so the ISIN itself is already written and survives a
        # rollback of the savepoint.
        try:
            with db.session.begin_nested():
                link_from_isin(user_id, isin)
        except Exception as e:
            logger.warning(f'Sweep link from ISIN failed for company '
                           f'{company.id}: {e}')
