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
Company identity matching.

A single company is listed under many tickers: the primary listing, foreign
cross-listings, and depositary receipts. Yahoo Finance returns all of them for
one query, so `Microsoft` yields MSFT, MSF.F, MSFT.NE and ZMSF.NE -- four rows
that read as the same company to a user.

Matching on the ticker string alone cannot collapse these, because the tickers
are genuinely different. These helpers derive a stable identity from the company
name instead, so cross-listings can be recognised as one company.
"""

import re

# Corporate form suffixes carry no identifying information -- "Apple Inc." and
# "APPLE INC" are the same company.
#
# Only true legal forms belong here. Words like GROUP or HOLDINGS are part of
# the trade name and distinguish real companies from one another, so stripping
# them would wrongly merge "Reliance Group" into "Reliance, Inc.".
_LEGAL_SUFFIXES = [
    'INCORPORATED', 'CORPORATION', 'COMPANY', 'LIMITED',
    'INC', 'CORP', 'LTD', 'PLC', 'LLC', 'LP',
    'NV', 'SA', 'AG', 'SE', 'AB', 'ASA', 'OYJ', 'SPA', 'BV',
]

_LEGAL_SUFFIX_RE = re.compile(
    r'\s+(?:' + '|'.join(_LEGAL_SUFFIXES) + r')\.?$'
)

# Parenthesised qualifiers describe the instrument, not the company:
# "MICROSOFT CDR (CAD HEDGED)", "APPLE INC CEDEAR(REPR 1/20 SHR)".
_PARENTHETICAL_RE = re.compile(r'\([^)]*\)?')

_PUNCTUATION_RE = re.compile(r'[^A-Z0-9 ]+')
_WHITESPACE_RE = re.compile(r'\s+')

# Wrapper instruments that track a company without being a listing of it.
# ADRs are deliberately absent: for many foreign companies the ADR is the only
# practical way for a user to hold the stock, so it is a legitimate result.
_DERIVATIVE_RE = re.compile(
    r'\b(?:CEDEAR|CDRS?|TOKENIZED|XSTOCK|WARRANTS?|RIGHTS)\b'
)

# Yahoo returns ETFs, indices, options and crypto alongside equities. Only
# equities can be held as a company position in a portfolio.
_EQUITY_QUOTE_TYPE = 'EQUITY'


def normalize_company_name(name):
    """
    Reduce a company name to a comparable core.

    "Microsoft Corporation", "MICROSOFT CORP." and "Microsoft Corporation "
    all reduce to "MICROSOFT".

    Returns an empty string when nothing identifying survives.
    """
    if not name:
        return ''

    normalized = _PARENTHETICAL_RE.sub(' ', name.upper())
    normalized = _PUNCTUATION_RE.sub(' ', normalized)
    normalized = _WHITESPACE_RE.sub(' ', normalized).strip()

    # Repeat: "Reliance Industries Ltd. Inc" carries two stackable suffixes.
    previous = None
    while previous != normalized:
        previous = normalized
        normalized = _LEGAL_SUFFIX_RE.sub('', normalized).strip()

    return normalized


def base_ticker(ticker_symbol):
    """
    Strip the exchange suffix from a ticker: "MSFT.NE" -> "MSFT".

    Used only as a fallback identity when a listing has no usable name.
    """
    if not ticker_symbol:
        return ''
    return ticker_symbol.upper().split('.')[0].strip()


def company_identity_key(name, ticker_symbol=None):
    """
    Build a key that is equal for two listings of the same company.

    The normalized name is the identity. The base ticker is only a fallback,
    because distinct companies routinely share a base ticker across exchanges
    (India's RELIANCE.NS versus an unrelated US RELIANCE would collide).
    """
    normalized = normalize_company_name(name)
    if normalized:
        return normalized
    return base_ticker(ticker_symbol)


def is_tradeable_equity(result):
    """
    Whether a provider search result is a real equity listing of a company.

    Rejects non-equity instruments (ETFs, crypto, indices) and wrapper
    instruments such as CDRs and CEDEARs, which duplicate a company the user
    can already reach through its ordinary listing.
    """
    quote_type = (result.get('quote_type') or '').upper()
    if quote_type and quote_type != _EQUITY_QUOTE_TYPE:
        return False

    name = (result.get('name') or '').upper()
    if _DERIVATIVE_RE.search(name):
        return False

    return True
