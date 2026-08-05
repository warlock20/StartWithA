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

"""Static contract checks on the inbox template. No app or DB needed.

The Tabulator formatters build HTML by string concatenation, so every
interpolation of user-controlled text has to go through escapeHtml.
"""

import os

INBOX = os.path.join(
    os.path.dirname(__file__), '..', 'app/ideas/templates/inbox.html')


def _inbox():
    return open(INBOX, encoding='utf-8').read()


def test_escape_helper_is_defined():
    assert 'function escapeHtml(' in _inbox()


def test_escape_helper_covers_all_five_dangerous_characters():
    s = _inbox()
    for pattern in ('&amp;', '&lt;', '&gt;', '&quot;', '&#39;'):
        assert pattern in s, f'escapeHtml does not emit {pattern}'


def test_name_and_ticker_are_escaped():
    s = _inbox()
    assert 'escapeHtml(cell.getValue())' in s
    assert 'escapeHtml(row.ticker)' in s


def test_source_is_escaped():
    assert "'<span class=\"idea-source-cell\">' + escapeHtml(val)" in _inbox()


def test_idea_name_is_not_interpolated_into_an_inline_onclick():
    """A name containing a backslash or double quote used to break the button."""
    s = _inbox()
    assert 'onclick="openEvaluateModal(' not in s
    assert 'data-evaluate-id=' in s
