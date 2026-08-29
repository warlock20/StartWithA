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
ISIN validation.

An ISIN is 12 characters: a 2-letter ISO country code, a 9-character national
number, and a check digit. The check digit is computed over the first 11
characters with letters expanded to their A=10..Z=35 values, then the Luhn
algorithm applied from the right.

This catches transposed and mistyped digits at the point of entry. It cannot
catch a *valid* ISIN belonging to the wrong company -- no local check can, which
is why ISINs are entered by a human and never inferred.
"""


def normalize_isin(value):
    """Strip and uppercase. Empty or whitespace-only becomes None."""
    if value is None:
        return None
    cleaned = str(value).strip().upper()
    return cleaned or None


def _expand(body):
    """Letters to their numeric values: A=10 .. Z=35. Digits pass through."""
    out = []
    for ch in body:
        if ch.isdigit():
            out.append(ch)
        elif ch.isalpha():
            out.append(str(ord(ch) - 55))
        else:
            return None
    return ''.join(out)


def is_valid_isin(value):
    """True only for a 12-character ISIN whose check digit is correct."""
    if not value or not isinstance(value, str):
        return False
    if len(value) != 12:
        return False
    if not value.isascii():
        return False
    if not value[:2].isalpha() or not value[:2].isupper():
        return False
    if not value[2:].isalnum() or value[2:] != value[2:].upper():
        return False
    if not value[-1].isdigit():
        return False

    expanded = _expand(value[:-1])
    if expanded is None:
        return False

    total = 0
    # Luhn: double every second digit counting from the right of the body.
    for i, ch in enumerate(reversed(expanded)):
        digit = int(ch)
        if i % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit

    return (total + int(value[-1])) % 10 == 0
