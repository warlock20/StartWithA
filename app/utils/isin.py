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


# Exchanges where a listing reliably implies the issuer's domicile, and the
# ISIN country prefix that domicile produces.
#
# Deliberately short. Most venues list foreign issuers as a matter of course --
# Accenture is Irish (IE00B4BNMY34) on the NYSE, London is full of Jersey and
# Guernsey domiciles, and Frankfurt cross-lists the world. Naming those here
# would reject correct ISINs. Only markets that are closed to foreign primary
# listings in practice belong.
_STRICT_DOMICILE_EXCHANGES = {
    '.T': 'JP',     # Tokyo
    '.NS': 'IN',    # India, NSE
    '.BO': 'IN',    # India, BSE
    '.KS': 'KR',    # South Korea
    '.KQ': 'KR',    # South Korea, KOSDAQ
    '.SS': 'CN',    # Shanghai
    '.SZ': 'CN',    # Shenzhen
    '.TW': 'TW',    # Taiwan
}


def isin_plausible_for_listing(isin, ticker):
    """May this machine-proposed ISIN be accepted for a listing on *ticker*?

    False only when the ISIN's country prefix contradicts a venue that admits
    no foreign issuers -- yfinance returning CA89238H1091 for Toyota on 7203.T,
    a valid ISIN whose check digit proves nothing about whose it is.

    The asymmetry is the point. A false reject leaves the company with no ISIN,
    which is where it already was. A false accept writes an ISIN that
    link_from_isin then fans out across every user who holds it, as a link
    whose origin claims no judgement was needed. So a mismatch is evidence
    against, while a match is no evidence for: anything unrecognised returns
    True and leaves the decision to the human gate downstream.

    Never consulted for an ISIN a person typed. Those are already judgements.
    """
    isin = normalize_isin(isin)
    if not isin:
        return False

    if not ticker:
        return True

    _, dot, suffix = str(ticker).upper().rpartition('.')
    if not dot:
        return True

    expected = _STRICT_DOMICILE_EXCHANGES.get('.' + suffix)
    if expected is None:
        return True

    return isin[:2] == expected
