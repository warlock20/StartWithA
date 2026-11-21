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

"""An expected return entered as a CAGR or as a total is stored as a CAGR."""

import pytest
from werkzeug.datastructures import MultiDict

from app.services.expected_return import (
    ExpectedReturnError,
    cagr_from_total,
    expected_return_from_form,
    to_expected_cagr,
)


def test_cagr_from_total():
    assert cagr_from_total(50, 36) == pytest.approx(14.47)
    assert cagr_from_total(10, 6) == pytest.approx(21.0)
    assert cagr_from_total(25, 12) == pytest.approx(25.0)
    assert cagr_from_total(-30, 24) == pytest.approx(-16.33)


def test_a_cagr_is_stored_as_entered():
    assert to_expected_cagr(15, 'cagr', 36) == 15
    assert to_expected_cagr(15, None, None) == 15


def test_a_total_is_converted_with_its_timeframe():
    assert to_expected_cagr(50, 'total', 36) == pytest.approx(14.47)


def test_a_total_needs_a_timeframe():
    with pytest.raises(ExpectedReturnError):
        to_expected_cagr(50, 'total', None)


def test_an_unknown_basis_is_refused():
    with pytest.raises(ExpectedReturnError):
        to_expected_cagr(50, 'monthly', 12)


def test_no_value_is_no_target():
    assert to_expected_cagr(None, 'total', None) is None
    assert expected_return_from_form(MultiDict()).cagr is None


def test_form_converts_a_total():
    form = MultiDict({'expected_return': '50', 'expected_return_basis': 'total', 'expected_timeframe': '36'})
    expected = expected_return_from_form(form)
    assert (expected.cagr, expected.timeframe_months) == (pytest.approx(14.47), 36)


def test_form_uses_the_first_filled_in_set_of_fields():
    # The buy form's no-research section repeats the fields after the main section
    form = MultiDict([
        ('expected_return', ''), ('expected_return_basis', 'cagr'), ('expected_timeframe', ''),
        ('expected_return', '21'), ('expected_return_basis', 'total'), ('expected_timeframe', '24'),
    ])
    assert expected_return_from_form(form).cagr == pytest.approx(10.0)


def test_form_rejects_a_timeframe_below_one_month():
    with pytest.raises(ExpectedReturnError):
        expected_return_from_form(MultiDict({'expected_return': '10', 'expected_timeframe': '0'}))


def test_plain_dict_forms_work_too():
    assert expected_return_from_form({'expected_return': '12'}).cagr == 12
