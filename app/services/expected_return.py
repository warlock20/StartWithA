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

"""Turn an expected return as entered into the expected CAGR that is stored.

The buy form and Update Thesis take the expected return either as a CAGR (% a
year) or as a total % over the expected timeframe. Only the CAGR is stored, and
Thesis vs Reality compares it with the position's CAGR.
"""

from dataclasses import dataclass
from typing import Optional

BASIS_CAGR = 'cagr'
BASIS_TOTAL = 'total'
BASES = (BASIS_CAGR, BASIS_TOTAL)
VALUE_FIELD = 'expected_return'
BASIS_FIELD = 'expected_return_basis'
TIMEFRAME_FIELD = 'expected_timeframe'


class ExpectedReturnError(ValueError):
    """The expected return as entered can't be turned into a CAGR."""


def cagr_from_total(total_pct: float, months: int) -> float:
    """The annual rate (CAGR, %) that compounds to total_pct over months."""
    growth = max(1 + float(total_pct) / 100, 0.0)
    return round((growth ** (12 / months) - 1) * 100, 2)


def to_expected_cagr(value: Optional[float], basis: Optional[str], months: Optional[int]) -> Optional[float]:
    """The CAGR to store for a value entered on basis ('cagr' or 'total')."""
    if value is None:
        return None
    basis = basis or BASIS_CAGR
    if basis not in BASES:
        raise ExpectedReturnError('Choose whether the expected return is a year or a total')
    if basis == BASIS_CAGR:
        return float(value)
    if not months:
        raise ExpectedReturnError('A total expected return needs the timeframe it is expected over')
    return cagr_from_total(value, months)


@dataclass
class ExpectedReturn:
    cagr: Optional[float]
    timeframe_months: Optional[int]


def _number(text, cast):
    try:
        return cast(text) if text not in (None, '') else None
    except (TypeError, ValueError):
        return None


def expected_return_from_form(form) -> ExpectedReturn:
    """Read the expected return, its basis and timeframe from a submitted form."""
    months = _number(form.get(TIMEFRAME_FIELD), int)
    if months is not None and months < 1:
        raise ExpectedReturnError('Expected timeframe must be at least 1 month')
    cagr = to_expected_cagr(_number(form.get(VALUE_FIELD), float), form.get(BASIS_FIELD), months)
    return ExpectedReturn(cagr, months)
